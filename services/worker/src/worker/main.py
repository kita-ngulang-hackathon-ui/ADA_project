"""Worker entry point: poll loop (python -m worker.main).

TODO:
- Load settings, build engine as app_worker.
- Loop: claim raw events -> normalize; claim queued runs -> pipeline.run_pipeline.
- Retry with backoff, stale claim recovery, SIGTERM handling.
"""


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
