"""The youtube-access engine with stub Google services, a fake ``secret`` CLI and a stub bridge."""

import importlib.util
import json
import os
from pathlib import Path
import stat

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ya = _load("youtube_access_engine_test", ROOT / "ya.py")
CID = "UC" + "a" * 22
CID2 = "UC" + "b" * 22
VID = "dQw4w9WgXcQ"


# --- fakes ----------------------------------------------------------------------------------------

class Req:
    def __init__(self, api, name, kwargs):
        self.api, self.name, self.kwargs = api, name, kwargs

    def execute(self):
        self.api.calls.append((self.name, self.kwargs))
        answer = self.api.answers.get(self.name, {})
        return answer(self.kwargs) if callable(answer) else answer


class Resource:
    def __init__(self, api, resource):
        self.api, self.resource = api, resource

    def __getattr__(self, method):
        return lambda **kwargs: Req(self.api, f"{self.resource}.{method}", kwargs)


class FakeAPI:
    def __init__(self, answers=None):
        self.answers = answers or {}
        self.calls = []

    def __getattr__(self, resource):
        if resource.startswith("_"):
            raise AttributeError(resource)
        return lambda: Resource(self, resource)


def video_item(vid=VID, channel=CID, **status):
    return {"id": vid, "snippet": {"title": f"title {vid}", "channelId": channel, "channelTitle": "Mine",
                                   "description": "desc", "tags": ["a"], "categoryId": "22",
                                   "publishedAt": "2026-01-01T00:00:00Z", "liveBroadcastContent": "none",
                                   "thumbnails": {"default": {}}},
            "statistics": {"viewCount": "10", "likeCount": "2", "commentCount": "1"},
            "contentDetails": {"duration": "PT1M5S"},
            "status": {"privacyStatus": "private", "uploadStatus": "processed", "embeddable": True,
                       "license": "youtube", "publicStatsViewable": True, "madeForKids": False,
                       "selfDeclaredMadeForKids": False, **status}}


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    store = tmp_path / "store"
    monkeypatch.setattr(ya, "STORE", store)
    monkeypatch.setattr(ya, "MIN_GAP", 0)
    monkeypatch.setattr(ya, "VENV_PYTHON", tmp_path / "python")
    (tmp_path / "python").write_text("")
    ya._CREDS.clear()
    ya._NARROW["ok"] = True
    return tmp_path


def authorize(*cids):
    ya._save_channels({cid: {"title": f"Chan {i}", "handle": f"@chan{i}"} for i, cid in enumerate(cids)})


def home_with(tmp_path, block: str) -> Path:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    (home / "config.yaml").write_text(block)
    return home


# --- references -----------------------------------------------------------------------------------

@pytest.mark.parametrize("value", [VID, f"https://www.youtube.com/watch?v={VID}", f"https://youtu.be/{VID}?t=3",
                                   f"https://youtube.com/shorts/{VID}", f"https://m.youtube.com/watch?feature=x&v={VID}",
                                   f"https://www.youtube.com/live/{VID}"])
def test_video_references(value):
    assert ya.video_id(value) == VID


@pytest.mark.parametrize("value", ["", "abc", "https://example.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ; rm -rf /"])
def test_bad_video_references(value):
    with pytest.raises(ya.YouTubeError):
        ya.video_id(value)


def test_channel_and_playlist_references():
    assert ya.channel_ref(CID) == ("id", CID)
    assert ya.channel_ref("@someone") == ("handle", "@someone")
    assert ya.channel_ref(f"https://www.youtube.com/channel/{CID}/videos") == ("id", CID)
    assert ya.channel_ref("https://www.youtube.com/@someone") == ("handle", "@someone")
    assert ya.playlist_id("https://www.youtube.com/playlist?list=PL1234567890abc") == "PL1234567890abc"
    with pytest.raises(ya.YouTubeError):
        ya.channel_ref("someone")
    with pytest.raises(ya.YouTubeError):
        ya.playlist_id(VID)


# --- channels and config --------------------------------------------------------------------------

def test_resolve_channel(tmp_path):
    with pytest.raises(ya.YouTubeError, match="yaccess auth"):
        ya.resolve_channel(None, None)
    authorize(CID)
    assert ya.resolve_channel(None, None)[0] == CID
    authorize(CID, CID2)
    with pytest.raises(ya.YouTubeError, match="several channels"):
        ya.resolve_channel(None, None)
    assert ya.resolve_channel("@chan1", None)[0] == CID2
    assert ya.resolve_channel("chan 1", None)[0] == CID2
    assert ya.resolve_channel(CID.lower(), None)[0] == CID
    home = home_with(tmp_path, "youtube_access:\n  default_channel: '@chan1'\n")
    assert ya.resolve_channel(None, home)[0] == CID2
    with pytest.raises(ya.YouTubeError, match="not an authorized channel"):
        ya.resolve_channel("@other", home)


def test_download_dir_follows_the_profile_config(tmp_path):
    home = home_with(tmp_path, "model: x\n")
    assert ya.download_dir(home) == home / "youtube-downloads"
    home = home_with(tmp_path, "youtube_access:\n  download_dir: ~/Workspaces/.inbox/youtube\n")
    assert ya.download_dir(home) == Path.home() / "Workspaces" / ".inbox" / "youtube"


def test_state_holds_no_secret_and_is_private(tmp_path):
    authorize(CID)
    ya.charge(units=1)
    assert stat.S_IMODE(os.stat(ya.STORE).st_mode) == 0o700
    text = "".join(p.read_text() for p in ya.STORE.glob("*.json"))
    assert "refresh" not in text


# --- quota and pacing -----------------------------------------------------------------------------

def test_quota_buckets(monkeypatch):
    ya.charge(units=ya.UNITS_STOP - 1)
    ya.charge(units=1)
    with pytest.raises(ya.YouTubeError, match="paused"):
        ya.charge(units=1)
    for _ in range(ya.SEARCH_DAILY):
        ya.charge(search=1)
    with pytest.raises(ya.YouTubeError, match="searches"):
        ya.charge(search=1)
    ya.charge(upload=1)  # its own bucket
    assert ya.usage()["api"]["units"] == ya.UNITS_STOP
    monkeypatch.setattr(ya, "_pacific_day", lambda: "2099-01-01")
    ya.charge(units=10, search=1)
    assert ya.usage()["api"] == {**ya.usage()["api"], "units": 10, "searches": 1, "uploads": 0}


def test_ytdlp_caps():
    for _ in range(ya.HOURLY):
        ya._pace_ytdlp()
    with pytest.raises(ya.YouTubeError, match="last hour"):
        ya._pace_ytdlp()


# --- Keychain -------------------------------------------------------------------------------------

def fake_secret(tmp_path, monkeypatch):
    """A ``secret`` CLI that keeps one value in a file and logs its argv."""
    script = tmp_path / "secret"
    value = tmp_path / "secret.value"
    log = tmp_path / "secret.log"
    script.write_text(f"""#!/bin/sh
echo "$*" >> {log}
case "$1" in
  get) [ -f {value} ] && cat {value} || exit 1 ;;
  show) [ -f {value} ] || exit 1 ;;
  set|update) cat > {value} ;;
esac
""")
    script.chmod(0o755)
    monkeypatch.setattr(ya, "SECRET", script)
    return value, log


def test_vault_round_trip_keeps_values_off_argv(tmp_path, monkeypatch):
    value, log = fake_secret(tmp_path, monkeypatch)
    assert ya.vault() == {"channels": {}}
    ya._vault_update(lambda d: d["channels"].__setitem__(CID, {"refresh_token": "rt-secret"}))
    ya._vault_update(lambda d: d["channels"].__setitem__(CID2, {"refresh_token": "rt-two"}))
    assert set(ya.vault()["channels"]) == {CID, CID2}
    lines = log.read_text().splitlines()
    first_write = next(line for line in lines if line.split()[0] in ("set", "update"))
    assert first_write.startswith("set YOUTUBE_OAUTH -p hermes --scope youtube-access -D token")
    assert first_write.endswith("--stdin")
    assert any(line.startswith("update YOUTUBE_OAUTH -p hermes --scope youtube-access") for line in lines)
    assert "rt-secret" not in log.read_text()
    value.write_text("not json")
    with pytest.raises(ya.YouTubeError, match="not JSON"):
        ya.vault()


class FakeCreds:
    instances = []

    def __init__(self, entry, read_only, fail=None, rotate=None):
        self.refresh_token = entry["refresh_token"]
        self.read_only = read_only
        self.narrow = read_only and ya._NARROW["ok"]
        self.valid = False
        self.fail = fail
        self.rotate = rotate
        self.granted_scopes = list(ya.READ_SCOPES) if self.narrow else list(ya.SCOPES)
        FakeCreds.instances.append(self)

    def refresh(self, request):
        from google.auth.exceptions import RefreshError
        if self.fail:
            message = self.fail(self)
            if message:
                raise RefreshError(message)
        if self.rotate:
            self.refresh_token = self.rotate
        self.valid = True


def test_credentials_narrow_reads_and_cache(tmp_path, monkeypatch):
    pytest.importorskip("google.auth")
    fake_secret(tmp_path, monkeypatch)
    ya._vault_update(lambda d: d["channels"].__setitem__(CID, {"refresh_token": "rt", "client_id": "c",
                                                               "client_secret": "s", "scopes": list(ya.SCOPES)}))
    FakeCreds.instances = []
    monkeypatch.setattr(ya, "_build_credentials", lambda cid, entry, read_only: FakeCreds(entry, read_only))
    read = ya.credentials(CID, True)
    assert read.narrow and ya.credentials(CID, True) is read
    write = ya.credentials(CID, False)
    assert not write.narrow and write is not read


def test_credentials_fall_back_when_google_will_not_narrow(tmp_path, monkeypatch):
    pytest.importorskip("google.auth")
    fake_secret(tmp_path, monkeypatch)
    ya._vault_update(lambda d: d["channels"].__setitem__(CID, {"refresh_token": "rt"}))
    monkeypatch.setattr(ya, "_build_credentials", lambda cid, entry, read_only: FakeCreds(
        entry, read_only, fail=lambda c: "invalid_scope: no" if c.narrow else None))
    creds = ya.credentials(CID, True)
    assert creds.valid and not creds.narrow and ya._NARROW["ok"] is False


def test_every_refresh_stores_a_rotated_refresh_token(tmp_path, monkeypatch):
    """The transport refreshes on its own (expiry, a 401 mid-upload); that path stores rotation too."""
    pytest.importorskip("google.oauth2.credentials")
    from google.oauth2.credentials import Credentials
    fake_secret(tmp_path, monkeypatch)
    entry = {"refresh_token": "old", "client_id": "c", "client_secret": "s", "scopes": list(ya.SCOPES)}
    ya._vault_update(lambda d: d["channels"].__setitem__(CID, dict(entry)))

    def google_refresh(self, request):
        self._refresh_token = "new"
        self.token = "access"
    monkeypatch.setattr(Credentials, "refresh", google_refresh)
    creds = ya._build_credentials(CID, entry, False)
    creds.refresh(object())  # as google_auth_httplib2 would, outside credentials()
    assert ya.vault()["channels"][CID]["refresh_token"] == "new"
    ya._vault_update(lambda d: d["channels"][CID].__setitem__("refresh_token", "newer"))
    stale = ya._build_credentials(CID, entry, False)  # refreshed from "old": must not clobber "newer"
    stale.refresh(object())
    assert ya.vault()["channels"][CID]["refresh_token"] == "newer"


def test_an_unreadable_vault_is_never_overwritten(tmp_path, monkeypatch):
    value, log = fake_secret(tmp_path, monkeypatch)
    ya._vault_update(lambda d: d["channels"].__setitem__(CID, {"refresh_token": "rt"}))
    script = Path(ya.SECRET)
    script.write_text(script.read_text().replace("get) [", "get) exit 1; ["))
    with pytest.raises(ya.YouTubeError, match="could not be read"):
        ya._vault_update(lambda d: d["channels"].__setitem__(CID2, {"refresh_token": "x"}))
    assert CID in json.loads(value.read_text())["channels"]


def test_credentials_refused_and_missing(tmp_path, monkeypatch):
    pytest.importorskip("google.auth")
    fake_secret(tmp_path, monkeypatch)
    with pytest.raises(ya.YouTubeError, match="yaccess auth"):
        ya.credentials(CID, True)
    ya._vault_update(lambda d: d["channels"].__setitem__(CID, {"refresh_token": "rt"}))
    monkeypatch.setattr(ya, "_build_credentials", lambda cid, entry, read_only: FakeCreds(
        entry, read_only, fail=lambda c: "invalid_grant: revoked"))
    with pytest.raises(ya.YouTubeError, match="re-runs `yaccess auth`"):
        ya.credentials(CID, True)


def test_a_cached_token_google_refuses_is_read_again(tmp_path, monkeypatch):
    pytest.importorskip("google.auth")
    fake_secret(tmp_path, monkeypatch)
    ya._vault_update(lambda d: d["channels"].__setitem__(CID, {"refresh_token": "old"}))
    monkeypatch.setattr(ya, "_build_credentials", lambda cid, entry, read_only: FakeCreds(
        entry, read_only, fail=lambda c: "invalid_grant" if c.refresh_token == "old" else None))
    stale = FakeCreds({"refresh_token": "old"}, True, fail=lambda c: "invalid_grant")
    ya._CREDS[(CID, True)] = stale
    ya._vault_update(lambda d: d["channels"][CID].__setitem__("refresh_token", "new"))
    assert ya.credentials(CID, True).refresh_token == "new"


# --- reads ----------------------------------------------------------------------------------------

@pytest.fixture
def api(monkeypatch):
    fake = FakeAPI()
    fake.read_only = []

    def service(cid, read_only, *a):
        fake.read_only.append(read_only)
        return fake
    monkeypatch.setattr(ya, "_service", service)
    return fake


def test_search_uses_the_search_bucket_and_adds_details(api):
    authorize(CID)
    api.answers = {"search.list": {"items": [{"id": {"videoId": VID}}]},
                   "videos.list": {"items": [video_item(channel=CID2)]}}
    out = ya.execute({"action": "search", "query": "  never   gonna ", "published_after": "2026-01-01"},
                     profile="marketer")
    assert out["results"][0]["views"] == 10 and out["results"][0]["duration_s"] == 65
    name, kwargs = api.calls[0]
    assert name == "search.list" and kwargs["q"] == "never gonna" and kwargs["publishedAfter"] == "2026-01-01T00:00:00Z"
    assert ya.usage()["api"]["searches"] == 1 and ya.usage()["api"]["units"] == 1
    assert set(api.read_only) == {True}


def test_my_videos_shows_private_status(api):
    authorize(CID)
    api.answers = {"channels.list": {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU" + "a" * 22}}}]},
                   "playlistItems.list": {"items": [{"id": "item1", "snippet": {"position": 0},
                                                     "contentDetails": {"videoId": VID}}]},
                   "videos.list": {"items": [video_item(publishAt="2026-12-01T00:00:00Z")]}}
    out = ya.execute({"action": "my_videos"}, profile="marketer")
    entry = out["videos"][0]
    assert entry["playlist_item_id"] == "item1" and entry["privacy"] == "private"
    assert entry["publish_at"] == "2026-12-01T00:00:00Z" and "description" not in entry


def test_comments_flatten_threads(api):
    authorize(CID)
    top = {"id": "Ugx" + "c" * 20, "snippet": {"authorDisplayName": "A", "textOriginal": "hi",
                                               "publishedAt": "t", "updatedAt": "t", "likeCount": 1}}
    api.answers = {"commentThreads.list": {"items": [{"snippet": {"topLevelComment": top, "totalReplyCount": 3},
                                                      "replies": {"comments": [top]}}]}}
    out = ya.execute({"action": "comments", "video": VID, "order": "time"}, profile="marketer")
    assert out["threads"][0]["reply_count"] == 3 and out["threads"][0]["replies"][0]["text"] == "hi"
    assert api.calls[0][1]["order"] == "time"


def test_analytics_defaults(api, monkeypatch):
    authorize(CID)
    seen = {}

    class Analytics:
        def reports(self):
            return self

        def query(self, **kwargs):
            seen.update(kwargs)
            return Req(api, "reports.query", kwargs)

    import types
    monkeypatch.setitem(__import__("sys").modules, "googleapiclient.discovery",
                        types.SimpleNamespace(build=lambda *a, **k: Analytics()))
    monkeypatch.setattr(ya, "credentials", lambda cid, read_only: object())
    api.answers = {"reports.query": {"columnHeaders": [{"name": "video"}, {"name": "views"}], "rows": [[VID, 5]]},
                   "videos.list": {"items": [video_item()]}}
    out = ya.execute({"action": "analytics", "dimensions": "video", "end": "2026-10-04"}, profile="marketer")
    assert seen["ids"] == "channel==MINE" and seen["startDate"] == "2026-09-07"
    assert seen["sort"] == "-views" and seen["maxResults"] == 50
    assert out["titles"] == {VID: f"title {VID}"}
    with pytest.raises(ya.YouTubeError):
        ya.execute({"action": "analytics", "filters": "country==JP; DROP"}, profile="marketer")


# --- transcripts and downloads --------------------------------------------------------------------

def test_transcript_formats_and_saves(tmp_path, monkeypatch):
    calls = []

    def bridge(op, deadline, **fields):
        calls.append((op, fields))
        return {"ok": True, "data": {"info": {"title": "T", "channel": "C", "duration": 70},
                                     "track": {"language": "en-orig", "kind": "auto",
                                               "events": [[0, "hello"], [65000, "world"], [3725000, "late"]]}}}
    monkeypatch.setattr(ya, "bridge", bridge)
    home = home_with(tmp_path, "model: x\n")
    out = ya.execute({"action": "transcript", "video": f"https://youtu.be/{VID}", "languages": ["en"]},
                     home=home, profile="marketer")
    assert out["text"] == "[0:00] hello\n[1:05] world\n[1:02:05] late"
    assert Path(out["path"]) == home / "youtube-downloads" / VID / f"{VID}.en-orig.txt"
    assert Path(out["path"]).read_text().startswith("[0:00] hello")
    assert calls == [("transcript", {"id": VID, "languages": ["en"]})]
    assert "mishear" in out["note"]
    plain = ya.execute({"action": "transcript", "video": VID, "timestamps": False}, home=home, profile="marketer")
    assert plain["text"] == "hello\nworld\nlate" and plain["path"].endswith(".plain.txt")


def test_download_lands_in_the_video_folder(tmp_path, monkeypatch):
    seen = {}

    def bridge(op, deadline, **fields):
        seen.update(fields, op=op, deadline=deadline)
        return {"ok": True, "data": {"info": {"title": "T"}, "files": [{"path": "/x.mp4", "bytes": 1}]}}
    monkeypatch.setattr(ya, "bridge", bridge)
    home = home_with(tmp_path, "youtube_access:\n  download_dir: " + str(tmp_path / "inbox") + "\n")
    out = ya.execute({"action": "download", "video": VID, "max_height": 720}, home=home, profile="assistant")
    assert seen["dir"] == str(tmp_path / "inbox" / VID) and seen["max_height"] == 720 and seen["kind"] == "video"
    assert out["files"] == [{"path": "/x.mp4", "bytes": 1}]
    with pytest.raises(ya.YouTubeError, match="max_height"):
        ya.execute({"action": "download", "video": VID, "max_height": 999}, home=home, profile="assistant")


def test_engine_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ya, "VENV_PYTHON", tmp_path / "nope")
    with pytest.raises(ya.YouTubeError, match="youtube-access.sh install"):
        ya.execute({"action": "transcript", "video": VID}, profile="marketer")
    assert ya.usage()["ytdlp"]["last_day"] == 0  # not counted


# --- guard ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("tool,args", [
    ("terminal", {"command": "yt-dlp https://youtu.be/x"}),
    ("terminal", {"command": "python -m yt_dlp x"}),
    ("terminal", {"command": "yaccess check"}),
    ("terminal", {"command": "cat ~/.youtube-access/state.json"}),
    ("terminal", {"command": "secret get YOUTUBE_OAUTH -p hermes --scope youtube-access"}),
    ("terminal", {"command": "security find-generic-password -s secret.hermes/youtube-access -w"}),
    ("terminal", {"command": "ls", "workdir": "/Users/x/.config/hermes/local/yt-dlp"}),
    ("read_file", {"path": "/Users/x/.youtube-access/channels.json"}),
    ("search_files", {"pattern": "YOUTUBE_OAUTH"}),
    ("terminal", {"command": "security dump-keychain -d ~/Library/Keychains/login.keychain-db"}),
    ("terminal", {"command": "secret export -p hermes --format json"}),
])
def test_bypass_blocked(tool, args):
    assert ya.bypass(tool, args) == ya.BYPASS_MESSAGE


@pytest.mark.parametrize("tool,args", [
    ("terminal", {"command": "ls ~/Workspaces/.inbox/youtube"}),
    ("terminal", {"command": "ffprobe ~/.hermes/profiles/assistant/youtube-downloads/x/x.mp4"}),
    ("read_file", {"path": "/Users/x/Workspaces/.inbox/youtube/abc/abc.en.txt"}),
    ("read_file", {"path": "/Users/x/.config/hermes/plugins/youtube-access/ya.py"}),
    ("web_search", {"query": "yt-dlp"}),
])
def test_bypass_allowed(tool, args):
    assert ya.bypass(tool, args) is None


def test_cli_paths(capsys):
    assert ya.main(["paths"]) == 0
    assert json.loads(capsys.readouterr().out)["keychain"].startswith("YOUTUBE_OAUTH")


# --- pacing ---------------------------------------------------------------------------------------

def test_one_ytdlp_call_at_a_time(monkeypatch):
    monkeypatch.setattr(ya, "LOCK_WAIT", 0.2)
    monkeypatch.setattr(ya, "bridge", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran")))
    with ya._lock("ytdlp.lock"):
        with pytest.raises(ya.YouTubeError, match="another transcript or download"):
            ya.execute({"action": "transcript", "video": VID}, profile="marketer")
