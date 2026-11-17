//! The lifetime of a runtime that the autostart hook started (ADR 0031, sections 2 and 3).
//!
//! An owned runtime (`serve --owner-session`) keeps the set of its owners: one key per agent
//! session (`<session_id>`) or subagent (`<session_id>/<agent_id>`) that attached to it. An owner
//! leaves by `runtime.release`, when the process it named is dead or its pid now belongs to
//! another process, or when it has not attached again for the time to live. The accept loop asks
//! [`Lifetime::should_exit`] once a second and stops the runtime only when no owner is left, no
//! connection is open and the caller proves the store idle. A runtime started by hand is not owned:
//! it records its owners but never stops by itself.

use std::collections::BTreeMap;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Mutex, MutexGuard};
use std::time::{Duration, Instant};

use serde_json::{Value, json};
use state::identity::{Identity, Verdict};
use state::mutex::lock_unpoisoned;

/// The time to live of an owner that never attaches again, unless `serve` names another.
pub const DEFAULT_OWNER_TTL: Duration = Duration::from_secs(3600);
/// The longest owner key.
pub const MAX_KEY_LEN: usize = 256;

/// One owner of the runtime.
#[derive(Debug)]
struct Owner {
    last_seen: Instant,
    /// The process the owner named, as the runtime observed it when it attached.
    identity: Option<Identity>,
}

/// The owners and the connections of one runtime.
#[derive(Debug)]
pub struct Lifetime {
    owned: bool,
    ttl: Duration,
    owners: Mutex<BTreeMap<String, Owner>>,
    exiting: AtomicBool,
    connections: AtomicUsize,
}

impl Default for Lifetime {
    fn default() -> Self {
        Self::manual()
    }
}

/// Whether `key` is an owner key: 1 to 256 characters of `[A-Za-z0-9._:/-]`.
pub fn valid_key(key: &str) -> bool {
    (1..=MAX_KEY_LEN).contains(&key.len())
        && key
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"._:/-".contains(&byte))
}

impl Lifetime {
    /// The lifetime of a runtime started by hand: it never stops by itself.
    pub fn manual() -> Self {
        Self::new(false, DEFAULT_OWNER_TTL)
    }

    /// The lifetime of a runtime the autostart hook started: it stops once its owners are gone
    /// and the store is idle; an owner that does not attach again for `ttl` is gone.
    pub fn owned(ttl: Duration) -> Self {
        Self::new(true, ttl)
    }

    fn new(owned: bool, ttl: Duration) -> Self {
        Self {
            owned,
            ttl,
            owners: Mutex::new(BTreeMap::new()),
            exiting: AtomicBool::new(false),
            connections: AtomicUsize::new(0),
        }
    }

    fn owners(&self) -> MutexGuard<'_, BTreeMap<String, Owner>> {
        lock_unpoisoned(&self.owners)
    }

    pub fn is_owned(&self) -> bool {
        self.owned
    }

    pub fn is_exiting(&self) -> bool {
        self.exiting.load(Ordering::SeqCst)
    }

    /// Add `key` as an owner, or renew it; `identity` is the process it named, when the runtime
    /// observed one. A runtime that decided to stop adds nothing.
    pub fn attach(&self, key: &str, identity: Option<Identity>, now: Instant) {
        if self.is_exiting() {
            return;
        }
        let mut owners = self.owners();
        let owner = owners.entry(key.to_owned()).or_insert(Owner {
            last_seen: now,
            identity: None,
        });
        owner.last_seen = now;
        if identity.is_some() {
            owner.identity = identity;
        }
    }

    /// Remove the owner `key`; whether it was one.
    pub fn release(&self, key: &str) -> bool {
        self.owners().remove(key).is_some()
    }

    /// The keys of the owners.
    pub fn owner_keys(&self) -> Vec<String> {
        self.owners().keys().cloned().collect()
    }

    /// What `runtime.attach` and `runtime.release` answer besides their own field.
    pub fn describe(&self, busy: &[String]) -> Value {
        json!({
            "owned": self.owned,
            "owners": self.owner_keys(),
            "busy": busy,
            "exiting": self.is_exiting(),
        })
    }

    /// Remove every owner whose process `judge` finds dead or replaced, or that has not attached
    /// for the time to live; the keys removed.
    pub fn sweep_with(&self, now: Instant, judge: &dyn Fn(&Identity) -> Verdict) -> Vec<String> {
        let mut owners = self.owners();
        let gone: Vec<String> = owners
            .iter()
            .filter(|(_, owner)| {
                now.saturating_duration_since(owner.last_seen) > self.ttl
                    || owner.identity.as_ref().is_some_and(|identity| {
                        matches!(judge(identity), Verdict::Dead | Verdict::PidReused)
                    })
            })
            .map(|(key, _)| key.clone())
            .collect();
        for key in &gone {
            owners.remove(key);
        }
        gone
    }

    /// [`Lifetime::sweep_with`] with the liveness verdict of this runtime.
    pub fn sweep(&self, now: Instant) -> Vec<String> {
        self.sweep_with(now, &|identity| state::identity::judge(Some(identity)))
    }

    /// A connection was accepted; the returned guard counts it until it is dropped.
    pub fn connection(self: &std::sync::Arc<Self>) -> ConnectionGuard {
        self.connections.fetch_add(1, Ordering::SeqCst);
        ConnectionGuard(std::sync::Arc::clone(self))
    }

    pub fn open_connections(&self) -> usize {
        self.connections.load(Ordering::SeqCst)
    }

    /// Whether an owned runtime stops now: after the sweep no owner is left, no connection is
    /// open and `idle` proves the store idle. The answer `true` is final: the runtime is exiting.
    /// The accept loop asks it on its own thread, so it accepts nothing after the decision. A
    /// connection the kernel queued in the backlog after the decision is closed at exit: the client
    /// sees `NotRunning` and `ensure` starts a new serve and retries.
    pub fn should_exit(&self, now: Instant, idle: impl FnOnce() -> bool) -> bool {
        if !self.owned {
            return false;
        }
        if self.is_exiting() {
            return true;
        }
        self.sweep(now);
        if !self.owners().is_empty() || self.open_connections() != 0 || !idle() {
            return false;
        }
        self.exiting.store(true, Ordering::SeqCst);
        true
    }
}

/// Counts one open connection of a [`Lifetime`].
#[derive(Debug)]
pub struct ConnectionGuard(std::sync::Arc<Lifetime>);

impl Drop for ConnectionGuard {
    fn drop(&mut self) {
        self.0.connections.fetch_sub(1, Ordering::SeqCst);
    }
}

#[cfg(test)]
mod tests {
    use std::sync::Arc;

    use super::*;

    fn identity(pid: i64) -> Identity {
        Identity {
            host: "h".to_owned(),
            boot_id: None,
            pid_namespace: None,
            pid,
            start_time: "1".to_owned(),
        }
    }

    fn alive(_: &Identity) -> Verdict {
        Verdict::Alive
    }

    #[test]
    fn owner_keys_are_short_and_plain() {
        assert!(valid_key("0b8c-session"));
        assert!(valid_key("s/agent-a8602610"));
        assert!(valid_key(&"k".repeat(MAX_KEY_LEN)));
        assert!(!valid_key(""));
        assert!(!valid_key(&"k".repeat(MAX_KEY_LEN + 1)));
        assert!(!valid_key("s agent"));
        assert!(!valid_key("s;rm"));
    }

    #[test]
    fn a_manual_runtime_never_exits_and_still_records_its_owners() {
        let lifetime = Lifetime::manual();
        lifetime.attach("s", None, Instant::now());

        assert!(!lifetime.should_exit(Instant::now(), || true));
        assert!(lifetime.release("s"));
        assert!(!lifetime.should_exit(Instant::now(), || true));
        assert!(!lifetime.is_exiting());
    }

    #[test]
    fn an_owned_runtime_exits_once_its_last_owner_released_and_the_store_is_idle() {
        let lifetime = Lifetime::owned(DEFAULT_OWNER_TTL);
        let now = Instant::now();
        lifetime.attach("s", None, now);
        lifetime.attach("s/a", None, now);

        assert!(!lifetime.should_exit(now, || true));
        assert!(lifetime.release("s/a"));
        assert!(!lifetime.release("s/a"));
        assert!(!lifetime.should_exit(now, || true));
        assert!(lifetime.release("s"));
        assert!(
            !lifetime.should_exit(now, || false),
            "a busy store keeps it"
        );
        assert!(lifetime.should_exit(now, || true));
        assert!(lifetime.is_exiting());
    }

    #[test]
    fn an_exiting_runtime_takes_no_new_owner() {
        let lifetime = Lifetime::owned(DEFAULT_OWNER_TTL);
        assert!(lifetime.should_exit(Instant::now(), || true));

        lifetime.attach("s", None, Instant::now());

        assert!(lifetime.owner_keys().is_empty());
        assert_eq!(lifetime.describe(&[])["exiting"], true);
    }

    #[test]
    fn an_open_connection_keeps_an_owned_runtime() {
        let lifetime = Arc::new(Lifetime::owned(DEFAULT_OWNER_TTL));
        let guard = lifetime.connection();

        assert_eq!(lifetime.open_connections(), 1);
        assert!(!lifetime.should_exit(Instant::now(), || true));
        drop(guard);
        assert!(lifetime.should_exit(Instant::now(), || true));
    }

    #[test]
    fn an_owner_that_does_not_attach_again_within_the_time_to_live_is_gone() {
        let lifetime = Lifetime::owned(Duration::from_secs(10));
        let start = Instant::now();
        lifetime.attach("old", None, start);
        lifetime.attach("renewed", None, start);
        lifetime.attach("renewed", None, start + Duration::from_secs(8));

        let gone = lifetime.sweep_with(start + Duration::from_secs(11), &alive);

        assert_eq!(gone, vec!["old".to_owned()]);
        assert_eq!(lifetime.owner_keys(), vec!["renewed".to_owned()]);
    }

    #[test]
    fn an_owner_whose_process_is_dead_or_replaced_is_gone_and_an_unknown_one_stays() {
        let lifetime = Lifetime::owned(DEFAULT_OWNER_TTL);
        let now = Instant::now();
        lifetime.attach("dead", Some(identity(1)), now);
        lifetime.attach("reused", Some(identity(2)), now);
        lifetime.attach("unknown", Some(identity(3)), now);
        lifetime.attach("alive", Some(identity(4)), now);
        lifetime.attach("unnamed", None, now);

        let gone = lifetime.sweep_with(now, &|identity| match identity.pid {
            1 => Verdict::Dead,
            2 => Verdict::PidReused,
            3 => Verdict::Unknown,
            _ => Verdict::Alive,
        });

        assert_eq!(gone, vec!["dead".to_owned(), "reused".to_owned()]);
        assert_eq!(
            lifetime.owner_keys(),
            vec![
                "alive".to_owned(),
                "unknown".to_owned(),
                "unnamed".to_owned()
            ]
        );
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn the_owner_of_a_finished_child_process_is_judged_dead() {
        let lifetime = Lifetime::owned(DEFAULT_OWNER_TTL);
        let mut child = std::process::Command::new("sleep")
            .arg("30")
            .spawn()
            .unwrap();
        let pid = i64::from(child.id());
        let observed = state::identity::observe(pid, &state::identity::observer());
        assert!(observed.is_some());
        lifetime.attach("child", observed, Instant::now());
        assert!(lifetime.sweep(Instant::now()).is_empty());

        child.kill().unwrap();
        child.wait().unwrap();

        assert_eq!(lifetime.sweep(Instant::now()), vec!["child".to_owned()]);
    }
}
