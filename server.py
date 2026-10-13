# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2,<2", "httpx"]
# ///
"""Read-only MCP server for HUJI Moodle (web service token auth)."""
import os
import time
from urllib.parse import unquote

import httpx
from mcp.server.fastmcp import FastMCP

BASE = os.environ.get("MOODLE_URL", "https://moodle.huji.ac.il/2026-27").rstrip("/")
TOKEN = os.environ["MOODLE_TOKEN"]

mcp = FastMCP("moodle")
_userid = None


def call(fn: str, **params):
    data = {"wstoken": TOKEN, "wsfunction": fn, "moodlewsrestformat": "json"}
    for k, v in params.items():
        if isinstance(v, list):
            for i, item in enumerate(v):
                data[f"{k}[{i}]"] = item
        elif v is not None:
            data[k] = v
    # HUJI's server intermittently resets connections; retry a few times.
    for attempt in range(4):
        try:
            r = httpx.post(f"{BASE}/webservice/rest/server.php", data=data, timeout=60)
            r.raise_for_status()
            break
        except httpx.TransportError:
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))
    out = r.json()
    if isinstance(out, dict) and out.get("exception"):
        raise RuntimeError(f"{out.get('errorcode')}: {out.get('message')}")
    return out


def userid():
    global _userid
    if _userid is None:
        _userid = call("core_webservice_get_site_info")["userid"]
    return _userid


@mcp.tool()
def site_info() -> dict:
    """Current user and site info."""
    i = call("core_webservice_get_site_info")
    return {k: i.get(k) for k in ("sitename", "username", "fullname", "userid", "release")}


@mcp.tool()
def list_courses() -> list:
    """Courses the user is enrolled in."""
    cs = call("core_enrol_get_users_courses", userid=userid())
    return [{"id": c["id"], "shortname": c.get("shortname"), "fullname": c.get("fullname")} for c in cs]


@mcp.tool()
def course_contents(course_id: int) -> list:
    """Sections, activities, and resource files of a course."""
    out = []
    for s in call("core_course_get_contents", courseid=course_id):
        mods = []
        for m in s.get("modules", []):
            mods.append({
                "id": m["id"], "name": m["name"], "type": m["modname"], "url": m.get("url"),
                "files": [{"name": f["filename"], "url": f.get("fileurl")}
                          for f in m.get("contents", []) if f.get("type") == "file"],
            })
        out.append({"section": s["name"], "summary": s.get("summary", "")[:500], "modules": mods})
    return out


@mcp.tool()
def assignments(course_id: int | None = None) -> list:
    """Assignments with due dates, optionally for one course."""
    res = call("mod_assign_get_assignments", courseids=[course_id] if course_id else None)
    out = []
    for c in res.get("courses", []):
        for a in c.get("assignments", []):
            out.append({
                "course": c.get("fullname"), "id": a["id"], "cmid": a.get("cmid"), "name": a["name"],
                "due": time.strftime("%Y-%m-%d %H:%M", time.localtime(a["duedate"])) if a.get("duedate") else None,
                "intro": (a.get("intro") or "")[:1000],
            })
    return out


@mcp.tool()
def upcoming_events() -> list:
    """Upcoming calendar events (deadlines, quizzes, etc.)."""
    res = call("core_calendar_get_calendar_upcoming_view")
    return [{
        "name": e["name"], "course": (e.get("course") or {}).get("fullname"),
        "time": time.strftime("%Y-%m-%d %H:%M", time.localtime(e["timestart"])),
        "type": e.get("modulename") or e.get("eventtype"), "url": e.get("url"),
    } for e in res.get("events", [])]


@mcp.tool()
def grades(course_id: int) -> list:
    """Grade items for the current user in a course."""
    res = call("gradereport_user_get_grade_items", courseid=course_id, userid=userid())
    return [{"item": g.get("itemname"), "grade": g.get("gradeformatted"), "range": g.get("rangeformatted"),
             "feedback": g.get("feedback")}
            for ug in res.get("usergrades", []) for g in ug.get("gradeitems", [])]


@mcp.tool()
def forum_discussions(forum_id: int) -> list:
    """Discussions in a forum (forum_id is the forum instance id, not cmid)."""
    res = call("mod_forum_get_forum_discussions", forumid=forum_id, perpage=50)
    return [{"id": d["discussion"], "subject": d["subject"], "author": d.get("userfullname"),
             "message": (d.get("message") or "")[:1500],
             "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(d["timemodified"]))}
            for d in res.get("discussions", [])]


@mcp.tool()
def course_forums(course_id: int) -> list:
    """Forums in a course (returns forum instance ids)."""
    return [{"id": f["id"], "cmid": f.get("cmid"), "name": f["name"]}
            for f in call("mod_forum_get_forums_by_courses", courseids=[course_id])]


@mcp.tool()
def download_file(file_url: str, dest_dir: str = "~/Downloads/moodle") -> str:
    """Download a Moodle file (fileurl from course_contents) to a local folder; returns the path."""
    dest = os.path.expanduser(dest_dir)
    os.makedirs(dest, exist_ok=True)
    sep = "&" if "?" in file_url else "?"
    r = httpx.get(f"{file_url}{sep}token={TOKEN}", timeout=120, follow_redirects=True)
    r.raise_for_status()
    name = unquote(os.path.basename(file_url.split("?")[0])) or "file"
    path = os.path.join(dest, name)
    with open(path, "wb") as f:
        f.write(r.content)
    return path


if __name__ == "__main__":
    mcp.run()
