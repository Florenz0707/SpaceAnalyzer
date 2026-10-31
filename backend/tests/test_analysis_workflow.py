import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from test_snapshots import wait_for_scan

from spaceanalyzer.analysis.models.contracts import ModelEvent, ModelRequest, ModelSpec
from spaceanalyzer.analysis.models.registry import ModelRegistry
from spaceanalyzer.analysis.workflow import AnalysisWorkflow
from spaceanalyzer.services.snapshots import SnapshotService


class ScriptedAdapter:
    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []
        self.gate: asyncio.Event | None = None
        self.entered = asyncio.Event()

    async def check_connection(self) -> bool:
        return True

    async def generate(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        self.requests.append(request)
        yield ModelEvent(kind="text", text="人工检查候选 [E1]")
        self.entered.set()
        if self.gate:
            await self.gate.wait()
        yield ModelEvent(kind="usage", input_tokens=10, output_tokens=4)
        yield ModelEvent(kind="finished", reason="stop")


async def finished(workflow: AnalysisWorkflow, run_id: str) -> None:
    for _ in range(200):
        if workflow.get_run(run_id).status not in {"queued", "running"}:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("Run did not finish")


def test_workflow_persistence_idempotency_cancel_and_cloud_consent(
    tmp_path: Path,
) -> None:
    root = tmp_path / "private"
    root.mkdir()
    (root / "secret.txt").write_bytes(b"abc")
    with SnapshotService(tmp_path / "state.sqlite3") as snapshots:
        snapshot_id = wait_for_scan(snapshots, snapshots.start_scan(str(root)).id)

        async def run() -> None:
            registry = ModelRegistry()
            adapter = ScriptedAdapter()
            registry.register(
                ModelSpec(key="local", provider="ollama", model_id="fixture"), adapter
            )
            registry.register(
                ModelSpec(key="cloud", provider="deepseek_api", model_id="fixture"),
                adapter,
            )
            workflow = AnalysisWorkflow(snapshots, registry)
            with pytest.raises(ValueError, match="consent"):
                workflow.create_conversation(snapshot_id, "cloud", False)
            conversation = workflow.create_conversation(snapshot_id, "local", False)
            first = await workflow.start_run(conversation.id, "分析占用", "first")
            await finished(workflow, first.id)
            result = workflow.get_run(first.id)
            assert result.status == "completed"
            assert "[E1]" in result.text
            assert result.usage == {"input_tokens": 10, "output_tokens": 4}
            assert len(result.evidence) == 5
            assert (
                await workflow.start_run(conversation.id, "分析占用", "first")
            ).id == first.id
            assert len(adapter.requests) == 1
            adapter.gate = asyncio.Event()
            adapter.entered.clear()
            second = await workflow.start_run(conversation.id, "继续", "second")
            await adapter.entered.wait()
            with pytest.raises(RuntimeError, match="active"):
                await workflow.start_run(conversation.id, "another", "third")
            await workflow.cancel(second.id)
            cancelled = workflow.get_run(second.id)
            assert cancelled.status == "cancelled"
            assert "人工检查" in cancelled.text
            assert len(adapter.requests[-1].messages) >= 4
            events = workflow.events(first.id, 0)
            assert [e.sequence for e in events] == list(range(1, len(events) + 1))
            assert workflow.events(first.id, events[-1].sequence) == []
            await workflow.close()
            reopened = AnalysisWorkflow(snapshots, registry)
            assert reopened.get_run(first.id).text == result.text
            await reopened.close()

        asyncio.run(run())


@pytest.mark.parametrize("failure", ["citation", "empty", "context", "interrupted"])
def test_analysis_failures_preserve_snapshot_and_recovery(
    tmp_path: Path, failure: str
) -> None:
    from spaceanalyzer.analysis.models.contracts import ModelCapacity

    class FaultyAdapter(ScriptedAdapter):
        async def generate(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
            if failure == "citation":
                yield ModelEvent(kind="text", text="Unsupported [E999]")
            yield ModelEvent(kind="finished", reason="stop")

    with SnapshotService(tmp_path / "state.sqlite3") as snapshots:
        root = tmp_path / "scan"
        root.mkdir()
        snapshot_id = wait_for_scan(snapshots, snapshots.start_scan(str(root)).id)

        async def run() -> None:
            registry = ModelRegistry()
            registry.register(
                ModelSpec(
                    key="fixture",
                    provider="ollama",
                    model_id="fixture",
                    capacity=ModelCapacity(
                        context_window=100 if failure == "context" else None
                    ),
                ),
                FaultyAdapter(),
            )
            workflow = AnalysisWorkflow(snapshots, registry)
            conversation = workflow.create_conversation(snapshot_id, "fixture", False)
            if failure == "interrupted":
                # Public persistence interface prepares a previously queued run.
                pending, _ = workflow.store.create_run(
                    conversation.id, "question", "interrupted"
                )
                reopened = AnalysisWorkflow(snapshots, registry)
                recovered = reopened.get_run(pending.id)
                assert recovered.status == "failed"
                assert recovered.error_code == "interrupted"
                assert reopened.events(pending.id, 0)[-1].kind == "terminal"
                await reopened.close()
            else:
                record = await workflow.start_run(conversation.id, "question", "failed")
                await finished(workflow, record.id)
                result = workflow.get_run(record.id)
                assert result.status == "failed"
                expected = {
                    "citation": "invalid_evidence",
                    "empty": "incomplete",
                    "context": "context_limit",
                }
                assert result.error_code == expected[failure]
            assert snapshots.get_snapshot(snapshot_id).status == "completed"
            await workflow.close()

        asyncio.run(run())
