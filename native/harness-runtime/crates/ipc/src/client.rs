//! The Unix client of the runtime that `harness-runtime ensure` and `release` use (ADR 0031,
//! section 4): connect to the socket, say `hello` with the token, then send requests.

use std::fs;
use std::io;
use std::os::unix::net::UnixStream;
use std::path::Path;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use contracts::{
    ErrorBody, FrameError, HelloPayload, PROTOCOL_VERSION, ProtocolVersion, Request, Response,
    Status, VersionRange, decode, encode, read_frame, write_frame,
};
use serde_json::Value;

use crate::paths::RuntimePaths;

/// How long one request waits for its answer.
const REQUEST_TIMEOUT: Duration = Duration::from_secs(10);

/// Why a request did not get an answer.
#[derive(Debug)]
pub enum ClientError {
    /// No runtime answers on the socket: no socket, no token, a refused connection, or a
    /// connection the runtime closed without an answer (a runtime that is stopping).
    NotRunning(String),
    /// The runtime answered with an error.
    Refused(ErrorBody),
    /// The answer broke the protocol, or the transport failed otherwise.
    Failed(String),
}

impl std::fmt::Display for ClientError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::NotRunning(reason) => write!(f, "no runtime answers: {reason}"),
            Self::Refused(error) => write!(f, "{} ({})", error.message, error.code.as_str()),
            Self::Failed(reason) => f.write_str(reason),
        }
    }
}

/// An authenticated connection to the runtime of one repository.
#[derive(Debug)]
pub struct Client {
    stream: UnixStream,
    negotiated: ProtocolVersion,
    features: Vec<String>,
    next: u64,
}

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |elapsed| {
            u64::try_from(elapsed.as_millis()).unwrap_or(u64::MAX)
        })
}

/// Whether an I/O error means that no runtime listens.
fn absent(err: &io::Error) -> bool {
    matches!(
        err.kind(),
        io::ErrorKind::NotFound
            | io::ErrorKind::ConnectionRefused
            | io::ErrorKind::ConnectionReset
            | io::ErrorKind::BrokenPipe
            | io::ErrorKind::UnexpectedEof
    )
}

impl Client {
    /// Connect to the runtime of `paths` and say `hello` for the repository `repo_root`.
    ///
    /// # Errors
    /// See [`ClientError`].
    pub fn connect(paths: &RuntimePaths, repo_root: &Path) -> Result<Self, ClientError> {
        let not_running = |what: &str, err: io::Error| {
            if absent(&err) {
                ClientError::NotRunning(format!("{what}: {err}"))
            } else {
                ClientError::Failed(format!("{what}: {err}"))
            }
        };
        let stream = UnixStream::connect(&paths.socket).map_err(|err| {
            not_running(&format!("cannot connect {}", paths.socket.display()), err)
        })?;
        let token = fs::read_to_string(&paths.token)
            .map_err(|err| not_running(&format!("cannot read {}", paths.token.display()), err))?;
        for timeout in [
            stream.set_read_timeout(Some(REQUEST_TIMEOUT)),
            stream.set_write_timeout(Some(REQUEST_TIMEOUT)),
        ] {
            timeout.map_err(|err| ClientError::Failed(err.to_string()))?;
        }
        let mut client = Self {
            stream,
            negotiated: PROTOCOL_VERSION,
            features: Vec::new(),
            next: 0,
        };
        let hello = HelloPayload {
            protocol: VersionRange {
                min: ProtocolVersion {
                    major: PROTOCOL_VERSION.major,
                    minor: 0,
                },
                max: PROTOCOL_VERSION,
            },
            client_version: env!("CARGO_PKG_VERSION").to_owned(),
            repo_root: repo_root.to_string_lossy().into_owned(),
            token: token.trim().to_owned(),
        };
        let payload =
            serde_json::to_value(hello).map_err(|err| ClientError::Failed(err.to_string()))?;
        let result = client.call("hello", Some(payload))?;
        if let Some(protocol) = result
            .get("protocol")
            .and_then(|value| serde_json::from_value(value.clone()).ok())
        {
            client.negotiated = protocol;
        }
        client.features = result
            .get("features")
            .and_then(Value::as_array)
            .map(|items| {
                items
                    .iter()
                    .filter_map(|item| item.as_str().map(str::to_owned))
                    .collect()
            })
            .unwrap_or_default();
        Ok(client)
    }

    /// Whether the runtime named `operation` in its `hello` features.
    pub fn serves(&self, operation: &str) -> bool {
        self.features.iter().any(|feature| feature == operation)
    }

    /// Send one request and give back its result.
    ///
    /// # Errors
    /// See [`ClientError`].
    pub fn call(&mut self, operation: &str, payload: Option<Value>) -> Result<Value, ClientError> {
        self.next += 1;
        let request = Request {
            protocol_version: self.negotiated,
            operation_id: format!("ensure-{}-{}", std::process::id(), self.next),
            operation: operation.to_owned(),
            request_deadline: now_ms() + 10_000,
            batch_id: None,
            dispatch_id: None,
            candidate_sha: None,
            plan_digest: None,
            expected_revision: None,
            fencing_token: None,
            payload,
        };
        let transport = |err: FrameError| match err {
            FrameError::Closed => {
                ClientError::NotRunning("the runtime closed the connection".to_owned())
            }
            FrameError::Io(err) if absent(&err) => ClientError::NotRunning(err.to_string()),
            other => ClientError::Failed(other.to_string()),
        };
        let body = encode(&request).map_err(|err| ClientError::Failed(err.to_string()))?;
        write_frame(&mut self.stream, &body).map_err(transport)?;
        let answer = read_frame(&mut self.stream).map_err(transport)?;
        let response: Response =
            decode(&answer).map_err(|err| ClientError::Failed(err.to_string()))?;
        match (response.status, response.result, response.error) {
            (Status::Ok, result, _) => Ok(result.unwrap_or(Value::Null)),
            (_, _, Some(error)) => Err(ClientError::Refused(error)),
            (_, _, None) => Err(ClientError::Failed(
                "the runtime answered an error without a body".to_owned(),
            )),
        }
    }
}
