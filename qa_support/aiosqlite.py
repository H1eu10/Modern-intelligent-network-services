"""QA-only SQLite adapter for offline environments lacking aiosqlite.
NOT a replacement for production dependency; excluded from release package.
"""
import sqlite3, asyncio
Error=sqlite3.Error
Row=sqlite3.Row
class Cursor:
 def __init__(self,c): self.c=c
 async def fetchone(self): return await asyncio.to_thread(self.c.fetchone)
 async def fetchall(self): return await asyncio.to_thread(self.c.fetchall)
 async def close(self): return await asyncio.to_thread(self.c.close)
class Connection:
 def __init__(self,c): self.c=c; self.lock=asyncio.Lock()
 @property
 def row_factory(self): return self.c.row_factory
 @row_factory.setter
 def row_factory(self,v): self.c.row_factory=v
 async def execute(self,*args):
  async with self.lock:return Cursor(await asyncio.to_thread(self.c.execute,*args))
 async def executemany(self,*args):
  async with self.lock:return Cursor(await asyncio.to_thread(self.c.executemany,*args))
 async def commit(self): await asyncio.to_thread(self.c.commit)
 async def close(self): await asyncio.to_thread(self.c.close)
 async def __aenter__(self): return self
 async def __aexit__(self,*args): await self.close()
async def connect(path,timeout=5):return Connection(await asyncio.to_thread(sqlite3.connect,path,timeout=timeout,check_same_thread=False))
