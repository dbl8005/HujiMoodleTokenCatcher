# HujiMoodleTokenCatcher

Get a Moodle web-service token for **Hebrew University (HUJI) Moodle** and connect Moodle to Claude Code (or any MCP client).

HUJI Moodle uses university SSO, so the usual `login/token.php` with a username and password does not work. This repo gets the token the way the official Moodle mobile app does.

## What's inside

| File | What it does |
|---|---|
| `get_token.py` | Opens a browser. You log in. It prints your token. |
| `server.py` | Read-only MCP server: courses, files, deadlines, assignments, grades, forums. |

## Quick start

1. Install [uv](https://docs.astral.sh/uv/): `brew install uv` (macOS) or see the uv docs.
2. Get your token:
   ```sh
   uv run get_token.py
   ```
   Log in in the browser window that opens (password, temporary code, or OTP all work). The token is printed in the terminal.
3. Connect it to Claude Code:
   ```sh
   claude mcp add moodle --scope user \
     -e MOODLE_TOKEN=<your token> \
     -- uv run --script "$(pwd)/server.py"
   ```
4. Restart Claude Code and ask: *"What's due on Moodle this week?"*

The default site is `https://moodle.huji.ac.il/2026-27`. For a different year or another SSO Moodle, pass the URL:

```sh
uv run get_token.py https://moodle.huji.ac.il/2027-28
```

and set `-e MOODLE_URL=https://moodle.huji.ac.il/2027-28` when adding the MCP server.

## How it works

1. The script opens Moodle's mobile-app launch URL:
   `/admin/tool/mobile/launch.php?service=moodle_mobile_app&passport=12345&urlscheme=moodlemobile`
2. Moodle sends you through SSO login.
3. After login, Moodle redirects to `moodlemobile://token=<base64>`, meant for the mobile app.
4. The script catches that redirect and decodes it: `signature:::TOKEN:::privatetoken`.

Your password never passes through this script. You type it into the real university login page.

## MCP tools

| Tool | Description |
|---|---|
| `site_info` | Your user and site info |
| `list_courses` | Enrolled courses |
| `course_contents` | Sections, activities, and file links of a course |
| `assignments` | Assignments with due dates |
| `upcoming_events` | Upcoming calendar events and deadlines |
| `grades` | Your grade items in a course |
| `course_forums` / `forum_discussions` | Forums and their posts |
| `download_file` | Download a course file to `~/Downloads/moodle` |

All tools are read-only.

## Notes

- **Keep your token private.** It gives read access to your Moodle account. Don't commit it.
- HUJI's server drops connections after a burst of fast requests. The MCP server retries, but avoid scripts that hammer the API.
- Not affiliated with the Hebrew University.

## License

MIT
