"""Confirmed feed-motion utilization, independent of HA and MQTT.

Only minute duration totals and current period counters are stored. Unobserved
scheduled time stays in the denominator, never in confirmed production time.
"""
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc


def shifts(day, zone):
    if day.weekday() >= 5:
        return []
    midnight = datetime.combine(day, datetime.min.time(), zone)
    result = []
    for number, offset in ((1, 6), (2, 16)):
        start = midnight + timedelta(hours=offset)
        end = start + timedelta(hours=10)
        breaks = [(start + timedelta(minutes=a), start + timedelta(minutes=b))
                  for a, b in ((150, 160), (300, 330), (450, 460))]
        result.append((f"{day.isoformat()}_{number}", start.timestamp(), end.timestamp(),
                       [(a.timestamp(), b.timestamp()) for a, b in breaks]))
    return result


def segments(start, end, zone):
    """Yield scheduled intervals, excluding breaks; anchor overnight to start day."""
    day = datetime.fromtimestamp(start, zone).date() - timedelta(days=1)
    last = datetime.fromtimestamp(end, zone).date()
    while day <= last:
        for identity, a, b, breaks in shifts(day, zone):
            cursor = a
            for c, d in breaks + [(b, b)]:
                left, right = max(start, cursor), min(end, c)
                if right > left:
                    yield identity, left, right
                cursor = d
        day += timedelta(days=1)


def planned(start, end, zone):
    return sum(b-a for _, a, b in segments(start, end, zone)) if end > start else 0


class Utilization:
    def __init__(self, path, timezone_name="America/Chicago"):
        self.zone = ZoneInfo(timezone_name)
        self.db = sqlite3.connect(path)
        if self.db.execute("PRAGMA user_version").fetchone()[0] not in (0,1):
            self.db.close()
            raise ValueError("Unsupported utilization database; restore a backup")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS machines(id INTEGER PRIMARY KEY, uuid TEXT UNIQUE NOT NULL);
        CREATE TABLE IF NOT EXISTS minutes(machine INTEGER, minute INTEGER, production REAL NOT NULL,
          observed REAL NOT NULL, PRIMARY KEY(machine,minute)) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS periods(machine INTEGER, period TEXT, start REAL NOT NULL,
          production REAL NOT NULL, observed REAL NOT NULL, PRIMARY KEY(machine,period)) WITHOUT ROWID;
        PRAGMA user_version=1;
        ''')
        self.previous = {}
        self.last_flush = time.monotonic()
        self.last_cleanup = 0

    def machine(self, identity):
        self.db.execute("INSERT OR IGNORE INTO machines(uuid) VALUES (?)", (identity,))
        return self.db.execute("SELECT id FROM machines WHERE uuid=?", (identity,)).fetchone()[0]

    def boundaries(self, stamp):
        local = datetime.fromtimestamp(stamp, self.zone)
        day = local.date()
        week = datetime.combine(day - timedelta(days=day.weekday()), datetime.min.time(), self.zone)
        month = datetime.combine(day.replace(day=1), datetime.min.time(), self.zone)
        # Shift ownership defines the production week/month, including Friday's overnight tail.
        for _, a, b, _ in shifts(day - timedelta(days=1), self.zone):
            if a <= stamp < b:
                anchor = datetime.fromtimestamp(a, self.zone).date()
                week = datetime.combine(anchor - timedelta(days=anchor.weekday()), datetime.min.time(), self.zone)
                month = datetime.combine(anchor.replace(day=1), datetime.min.time(), self.zone)
        return {"week": week.timestamp(), "month": month.timestamp()}

    def observe(self, identity, signals, stamp=None, max_gap=2):
        stamp = time.time() if stamp is None else stamp
        required = ("mode", "execution", "feed_rate")
        known = all(n in signals for n in required)
        production = known and signals["mode"]["value"] == "AUTOMATIC" and signals["execution"]["value"] == "ACTIVE" and signals["feed_rate"]["value"] > 0
        old = self.previous.get(identity)
        self.previous[identity] = (stamp, known, production)
        if old and known and old[1] and 0 < stamp-old[0] <= max_gap:
            machine = self.machine(identity)
            for shift, left, right in segments(old[0], stamp, self.zone):
                cursor = left
                while cursor < right:
                    end = min(right, (int(cursor // 60)+1)*60)
                    duration = end-cursor
                    # Both bounding observations must confirm production.
                    running = duration if production and old[2] else 0
                    minute = int(cursor // 60)*60
                    self.db.execute('''INSERT INTO minutes VALUES (?,?,?,?) ON CONFLICT(machine,minute)
                        DO UPDATE SET production=production+excluded.production, observed=observed+excluded.observed''',
                        (machine, minute, running, duration))
                    buckets = self.boundaries(cursor)
                    anchor = datetime.fromisoformat(shift[:10]).date()
                    shift_start = datetime.combine(anchor,datetime.min.time(),self.zone) + timedelta(hours=6 if shift[-1]=="1" else 16)
                    for name, start in {**buckets, "shift_"+shift[-1]: shift_start.timestamp()}.items():
                        self.db.execute('''INSERT INTO periods VALUES (?,?,?,?,?) ON CONFLICT(machine,period)
                            DO UPDATE SET start=excluded.start,
                            production=CASE WHEN start=excluded.start THEN production+excluded.production ELSE excluded.production END,
                            observed=CASE WHEN start=excluded.start THEN observed+excluded.observed ELSE excluded.observed END''',
                            (machine, name, start, running, duration))
                    cursor = end
        self.maintain(stamp)

    def gap(self, identity):
        self.previous.pop(identity, None)

    def maintain(self, stamp):
        if stamp - self.last_cleanup >= 60:
            cutoff = int((stamp - 7*86400) // 60 + 1)*60
            self.db.execute("DELETE FROM minutes WHERE minute < ?", (cutoff,))
            self.last_cleanup = stamp
        if time.monotonic() - self.last_flush >= 15:
            self.flush()

    def summary(self, identity, stamp=None):
        stamp = time.time() if stamp is None else stamp
        machine = self.machine(identity)
        self.maintain(stamp)
        windows = {"24h": (stamp-86400, stamp), **{k:(v,stamp) for k,v in self.boundaries(stamp).items()}}
        day = datetime.fromtimestamp(stamp,self.zone).date()
        for number in (1,2):
            candidates = [item for offset in range(8) for item in shifts(day-timedelta(days=offset),self.zone)
                          if item[0].endswith('_'+str(number)) and item[1] <= stamp]
            if candidates:
                _,a,b,_ = max(candidates,key=lambda s:s[1])
                windows['shift_'+str(number)] = (a,min(b,stamp))
        result = {}
        for name,(start,end) in windows.items():
            denominator = planned(start,end,self.zone)
            if name in ("week","month"):
                anchor = datetime.fromtimestamp(start,self.zone).date().isoformat()
                denominator = sum(b-a for shift,a,b in segments(start,end,self.zone) if shift[:10]>=anchor)
            if name == '24h':
                rows = self.db.execute("SELECT minute,production,observed FROM minutes WHERE machine=? AND minute+60>? AND minute<?",(machine,start,end)).fetchall()
                # Minute totals give rolling-window boundary accuracy of one minute.
                p = sum(p*max(0,min(m+60,end)-max(m,start))/60 for m,p,o in rows)
                o = sum(o*max(0,min(m+60,end)-max(m,start))/60 for m,p,o in rows)
            else:
                row = self.db.execute("SELECT start,production,observed FROM periods WHERE machine=? AND period=?",(machine,name)).fetchone()
                p,o = row[1:] if row and row[0] == start else (0,0)
            p,o = min(p,denominator),min(o,denominator)
            result[name] = {"production_seconds": round(p,2), "planned_seconds": round(denominator,2),
                            "unknown_seconds": round(max(0,denominator-o),2),
                            "utilization": round(100*p/denominator,2) if denominator else 0,
                            "coverage": round(100*o/denominator,2) if denominator else 0,
                            "start": datetime.fromtimestamp(start,UTC).isoformat(),
                            "end": datetime.fromtimestamp(end,UTC).isoformat()}
        return result

    def signals(self, identity, stamp=None):
        result = {}
        for period,values in self.summary(identity,stamp).items():
            for field,unit in (("utilization","%"),("coverage","%"),("production_seconds","s"),("planned_seconds","s"),("unknown_seconds","s")):
                result[f"production_{period}_{field}"] = {"value":values[field],"unit":unit,"kind":"sensor","source":"monitor.confirmed_feed_utilization","group":"utilization"}
        return result

    def remove(self, identity):
        row = self.db.execute("SELECT id FROM machines WHERE uuid=?",(identity,)).fetchone()
        if row:
            for table in ('minutes','periods'):
                self.db.execute(f"DELETE FROM {table} WHERE machine=?",(row[0],))
            self.db.execute("DELETE FROM machines WHERE id=?",(row[0],))
        self.gap(identity)
        self.flush()

    def flush(self):
        self.db.commit()
        self.db.execute("PRAGMA wal_checkpoint(PASSIVE)")
        self.last_flush = time.monotonic()

    def close(self):
        self.flush()
        self.db.close()
