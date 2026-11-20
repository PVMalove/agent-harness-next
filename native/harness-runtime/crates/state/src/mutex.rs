//! The lock of a mutex that a panicked holder poisoned. The data a runtime mutex guards (open
//! snapshots, fired test hooks, the executions a thread watches) stays consistent at every
//! unlock, so the runtime goes on with it instead of failing every later request.

use std::sync::{Mutex, MutexGuard, PoisonError};

/// Lock `mutex`, even when a holder panicked.
pub fn lock_unpoisoned<T>(mutex: &Mutex<T>) -> MutexGuard<'_, T> {
    mutex.lock().unwrap_or_else(PoisonError::into_inner)
}

#[cfg(test)]
mod tests {
    use std::panic;

    use super::*;

    #[test]
    fn a_poisoned_mutex_is_still_locked() {
        let mutex = Mutex::new(1);
        let poisoned = panic::catch_unwind(|| {
            let _held = mutex.lock().unwrap();
            panic!("the holder panics");
        });
        assert!(poisoned.is_err());
        assert!(mutex.is_poisoned());
        *lock_unpoisoned(&mutex) += 1;
        assert_eq!(*lock_unpoisoned(&mutex), 2);
    }
}
