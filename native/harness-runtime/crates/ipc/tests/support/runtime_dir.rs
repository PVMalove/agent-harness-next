//! A private scratch runtime directory (`XDG_RUNTIME_DIR`) for tests, removed when it drops.
//!
//! The runtime puts its socket at `<dir>/harness/<repo id>.sock`, and that path must fit
//! `MAX_SOCKET_PATH_BYTES`. Under a long `TMPDIR`, such as the per-run directory of the QA
//! container, it does not, so on Unix the directory moves to `/tmp` instead. On Unix the including
//! module brings `MAX_SOCKET_PATH_BYTES` into scope.

use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};

#[cfg(unix)]
use super::MAX_SOCKET_PATH_BYTES;

/// The bytes the runtime appends to the directory: `/harness/`, 16 hex digits and `.sock`.
#[cfg(unix)]
const SOCKET_SUFFIX_BYTES: usize = "/harness/".len() + 16 + ".sock".len();

pub struct RuntimeDir(PathBuf);

impl RuntimeDir {
    /// A new `0700` directory named after `name` under `TMPDIR`; on Unix under `/tmp` when the
    /// socket path under `TMPDIR` would exceed the limit.
    pub fn new(name: &str) -> Self {
        static NEXT: AtomicUsize = AtomicUsize::new(0);
        let n = NEXT.fetch_add(1, Ordering::Relaxed);
        let pid = std::process::id();
        let dir = Self::create(std::env::temp_dir().join(format!("hr-{name}-{pid}-{n}")));
        #[cfg(unix)]
        if dir.0.as_os_str().len() + SOCKET_SUFFIX_BYTES > MAX_SOCKET_PATH_BYTES {
            drop(dir);
            return Self::create(PathBuf::from(format!("/tmp/hr-{pid}-{n}")));
        }
        dir
    }

    fn create(path: PathBuf) -> Self {
        let _ = fs::remove_dir_all(&path);
        fs::create_dir_all(&path).unwrap();
        // Private whatever the umask: a runtime directory refuses a parent others may write.
        #[cfg(unix)]
        fs::set_permissions(
            &path,
            <fs::Permissions as std::os::unix::fs::PermissionsExt>::from_mode(0o700),
        )
        .unwrap();
        // The runtime measures the canonical path, as the tests compare against it.
        Self(fs::canonicalize(path).unwrap())
    }

    pub fn path(&self) -> &Path {
        &self.0
    }
}

impl Drop for RuntimeDir {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
