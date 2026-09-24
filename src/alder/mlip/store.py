"""SQLite transactions preserve input, incremental frames, and checkpoint associations."""
import json
from pathlib import Path
import sqlite3
import time
import uuid
import zlib
from .contract import canonical, digest

TERMINAL={'completed','unconverged','cancelled','failed','interrupted'}

def packed(value): return zlib.compress(canonical(value).encode(),3)
def unpacked(value): return json.loads(zlib.decompress(value))

class Store:
    def __init__(self, path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path,timeout=30)
        self.db.execute('PRAGMA journal_mode=WAL'); self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,input TEXT NOT NULL,input_hash TEXT NOT NULL,status TEXT NOT NULL,created REAL NOT NULL,started REAL,finished REAL,progress TEXT NOT NULL DEFAULT '{}',error TEXT, cancel INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS frames(job TEXT NOT NULL REFERENCES jobs(id),idx INTEGER NOT NULL,data BLOB NOT NULL,PRIMARY KEY(job,idx));
        CREATE TABLE IF NOT EXISTS artifacts(job TEXT NOT NULL REFERENCES jobs(id),name TEXT NOT NULL,data BLOB NOT NULL,PRIMARY KEY(job,name));
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,job TEXT NOT NULL REFERENCES jobs(id),time REAL NOT NULL,message TEXT NOT NULL);
        ''')
    def close(self): self.db.close()
    def submit(self, data):
        ident=uuid.uuid4().hex
        with self.db:
            self.db.execute('INSERT INTO jobs(id,input,input_hash,status,created) VALUES(?,?,?,?,?)',(ident,canonical(data),digest(data),'queued',time.time()))
        return ident
    def jobs(self):
        return [self.job(row[0],include_input=False) for row in self.db.execute('SELECT id FROM jobs ORDER BY created DESC')]
    def job(self,ident,include_input=True):
        cur=self.db.execute('SELECT * FROM jobs WHERE id=?',(ident,)); row=cur.fetchone()
        if row is None: raise ValueError('Unknown job.')
        result=dict(zip([d[0] for d in cur.description],row)); result['progress']=json.loads(result['progress'])
        if include_input:
            result['input']=json.loads(result['input'])
            if digest(result['input'])!=result['input_hash']: raise ValueError('Input snapshot failed its integrity check.')
        else: result.pop('input')
        return result
    def claim(self,ident):
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            if self.db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]: return False
            return self.db.execute("UPDATE jobs SET status='running',started=? WHERE id=? AND status='queued'",(time.time(),ident)).rowcount==1
    def state(self,ident,status,error=None):
        if status not in TERMINAL|{'queued','running','waiting'}: raise ValueError('Invalid job state.')
        with self.db:self.db.execute('UPDATE jobs SET status=?,error=?,finished=? WHERE id=?',(status,error,time.time() if status in TERMINAL else None,ident))
        parent=self.job(ident)['input'].get('parent')
        if status in TERMINAL and parent and self.job(parent['job'])['status']=='waiting':
            workflow=self.artifact(parent['job'],'workflow')
            if workflow and workflow['child']==ident:self.state(parent['job'],status,error)
    def cancel(self,ident):
        with self.db:
            self.db.execute('UPDATE jobs SET cancel=1 WHERE id=?',(ident,))
            self.db.execute("UPDATE jobs SET status='cancelled',finished=? WHERE id=? AND status='queued'",(time.time(),ident))
    def cancelled(self,ident): return bool(self.db.execute('SELECT cancel FROM jobs WHERE id=?',(ident,)).fetchone()[0])
    def event(self,ident,message):
        with self.db:self.db.execute('INSERT INTO events(job,time,message) VALUES(?,?,?)',(ident,time.time(),str(message)))
    def events(self,ident,limit=150):
        return list(reversed(self.db.execute('SELECT time,message FROM events WHERE job=? ORDER BY id DESC LIMIT ?',(ident,limit)).fetchall()))
    def frame(self,ident,data,checkpoint=None):
        with self.db:
            index=self.count(ident)
            self.db.execute('INSERT INTO frames VALUES(?,?,?)',(ident,index,packed(data)))
            if checkpoint is not None:self._artifact(ident,'checkpoint',checkpoint|{'frame':index})
        return index
    def count(self,ident): return self.db.execute('SELECT count(*) FROM frames WHERE job=?',(ident,)).fetchone()[0]
    def frames(self,ident,start=0,limit=200):
        if not 1<=limit<=1000: raise ValueError('Preview page must contain 1–1000 frames.')
        return [(i,unpacked(d)) for i,d in self.db.execute('SELECT idx,data FROM frames WHERE job=? AND idx>=? ORDER BY idx LIMIT ?',(ident,start,limit))]
    def get_frame(self,ident,index):
        row=self.db.execute('SELECT data FROM frames WHERE job=? AND idx=?',(ident,index)).fetchone()
        if row is None: raise ValueError('No saved geometry at this frame.')
        return unpacked(row[0])
    def _artifact(self,ident,name,value): self.db.execute('INSERT OR REPLACE INTO artifacts VALUES(?,?,?)',(ident,name,packed(value)))
    def artifact(self,ident,name,value=None):
        if value is not None:
            with self.db:self._artifact(ident,name,value)
            return value
        row=self.db.execute('SELECT data FROM artifacts WHERE job=? AND name=?',(ident,name)).fetchone()
        return unpacked(row[0]) if row else None
    def progress(self,ident,**value):
        with self.db:self.db.execute('UPDATE jobs SET progress=? WHERE id=?',(canonical(value),ident))
