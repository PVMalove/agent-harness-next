// Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
// SPDX-License-Identifier: BUSL-1.1
// Licensed under the Business Source License 1.1 (BSL-1.1).
// Commercial use, sale, or use in commercial application development is strictly
// prohibited without prior written permission from the copyright holder.
// Removing or altering this header is prohibited and voids all license rights.

//! The runtime store (ADR 0020): canonical JSON, the store schema, and the import of the file
//! ledger of installation 1.x.

pub mod approval;
pub mod archive;
pub mod audit;
pub mod authority;
pub mod canonical;
pub mod error;
pub mod executions;
pub mod export;
pub mod hooks;
pub mod identity;
pub mod idle;
pub mod import;
pub mod import_approval;
pub mod init;
pub mod lease;
pub mod legacy;
pub mod lock;
pub mod migrate;
pub mod mutex;
pub mod parity;
pub mod platform;
pub mod policy;
pub mod project;
pub mod qa_evidence;
pub mod read;
pub mod read_session;
pub mod repair;
pub mod rollback;
pub mod route;
pub mod schema;
pub mod snapshot;
pub mod store_error;
pub mod time;
pub mod validate;
pub mod vocabulary;
pub mod write;

pub use error::{Error, Result};
