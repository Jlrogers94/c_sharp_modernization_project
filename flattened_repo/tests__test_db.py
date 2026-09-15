from modernizer_agent.db import Database


def test_task_queue(tmp_path):
    db = Database(tmp_path / "index.db")
    db.create_task("MIG-2", "Later", None, 20, "ok")
    db.create_task("MIG-1", "First", None, 10, "ok")
    assert db.next_task()["task_key"] == "MIG-1"
    db.update_task("MIG-1", status="COMPLETE")
    assert db.next_task()["task_key"] == "MIG-2"
    db.close()
