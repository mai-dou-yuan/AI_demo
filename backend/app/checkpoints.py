"""Single-user adapter: short SQLite checkpoint operations on the owning loop.

Avoids a long-lived worker thread; graph network/model nodes remain async.
This is intentionally for the local demo, not a multi-user deployment.
"""
from langgraph.checkpoint.sqlite import SqliteSaver


class LocalSqliteSaver(SqliteSaver):
    async def aget_tuple(self, config):
        return self.get_tuple(config)

    async def alist(self, config, *, filter=None, before=None, limit=None):
        for value in self.list(config, filter=filter, before=before, limit=limit):
            yield value

    async def aput(self, config, checkpoint, metadata, new_versions):
        return self.put(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=''):
        self.put_writes(config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id):
        self.delete_thread(thread_id)
