"""Public rates replies. Fail closed; no third-party packages. Disabled by default."""
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, ROUND_HALF_UP

UTC = dt.timezone.utc
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
FEED = 'https://sonarkatta.github.io/1-rates.json'
RATE_KEYS = ('gold24_10g', 'gold22_10g', 'silver999_kg')
CTA = 'रोजच्या लाईव्ह अपडेट्ससाठी आमच्या YouTube, Instagram आणि Facebook वर लाईक करा, फॉलो करा आणि कमेंट करा - @sonarkatta'
TRIGGER = re.compile(r'(?<!\w)(?:rates?|prices?|live)(?!\w)|रेट|(?:^|\s)दर(?:\s|$|[?!,।])|भाव|किंमत', re.I)
NEGATIVE = re.compile(r'fake|fraud|spam|scam|wrong|खोट|फसव|चुकी', re.I)

class Stop(RuntimeError):
    pass

def timestamp(s):
    if not isinstance(s, str):
        raise Stop('missing_timestamp')
    try:
        x = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
        if x.tzinfo is None:
            raise ValueError()
        return x.astimezone(UTC)
    except ValueError:
        raise Stop('invalid_timestamp') from None

def eligible(text):
    return isinstance(text, str) and len(text) <= 2000 and bool(TRIGGER.search(text)) and not NEGATIVE.search(text)

def money(n):
    n = int((Decimal(n) / 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * 100)
    s = str(n)
    tail, head = s[-3:], s[:-3]
    groups = []
    while head:
        groups.insert(0, head[-2:]); head = head[:-2]
    return ','.join(groups + [tail])

def reply(feed, now=None):
    now = now or dt.datetime.now(UTC)
    captured = timestamp(feed.get('quote_timestamp'))
    age = (now - captured).total_seconds()
    if not -60 <= age <= 600:
        raise Stop('stale_or_future_feed')
    for key in RATE_KEYS:
        value = feed.get(key)
        if type(value) is not int or not 0 < value < 100000000:
            raise Stop('invalid_rate')
        if timestamp(feed.get(key + '_captured_at')) != captured:
            raise Stop('mixed_rate_timestamps')
    if abs(feed['gold22_10g'] / feed['gold24_10g'] - .916) > .004:
        raise Stop('inconsistent_gold')
    local = captured.astimezone(IST)
    return (f'ताजे सोने-चांदीचे दर ({local:%d-%m-%Y, %I:%M %p} IST):\n'
            f'24K सोने: ₹{money(feed["gold24_10g"])} / 10g\n'
            f'22K सोने: ₹{money(feed["gold22_10g"])} / 10g\n'
            f'चांदी 999: ₹{money(feed["silver999_kg"])} / kg\n'
            f'(GST extra)\n\n{CTA}')

def request(url, token=None, method='GET', data=None, form=False):
    headers = {'User-Agent': 'SonarKattaRates/1.0'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if data is not None:
        if form:
            data = urllib.parse.urlencode(data).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        else:
            data = json.dumps(data).encode()
            headers['Content-Type'] = 'application/json'
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=25) as r:
            raw = r.read(4000000)
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        # Never log provider bodies, tokens, private comments or query URLs.
        raise Stop('provider_http_' + str(e.code)) from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise Stop('network_or_decode_failure') from None

def query(url, params):
    return url + '?' + urllib.parse.urlencode(params)

class State:
    """Optimistic Contents API state on a dedicated branch. Only hashes and counters."""
    def __init__(self):
        self.base = 'https://api.github.com/repos/' + os.environ['GITHUB_REPOSITORY']
        self.token = os.environ['GITHUB_TOKEN']
        self.branch = 'comment-rates-state'
        self.path = '/contents/state.json'
        r = request(query(self.base + self.path, {'ref': self.branch}), self.token)
        import base64
        self.sha = r['sha']
        self.data = json.loads(base64.b64decode(r['content']))
        if self.data.get('schema') != 1:
            raise Stop('unknown_state_schema')
    def save(self):
        import base64
        r = request(self.base + self.path, self.token, 'PUT', {
            'message': 'Update rates reply dedupe ledger', 'branch': self.branch,
            'sha': self.sha,
            'content': base64.b64encode(json.dumps(self.data, sort_keys=True).encode()).decode()})
        self.sha = r['content']['sha']
    def reserve(self, platform, comment_id):
        key = hashlib.sha256((platform + ':' + comment_id).encode()).hexdigest()
        if key in self.data['seen']:
            return None
        now = dt.datetime.now(UTC)
        recent = [x for x in self.data['counts'].get(platform, [])
                  if (now - timestamp(x)).total_seconds() < 86400]
        limit = 80 if platform == 'youtube' else 100
        if len(recent) >= limit:
            raise Stop('daily_reply_cap')
        self.data['counts'][platform] = recent + [now.isoformat()]
        self.data['seen'][key] = {'status': 'reserved', 'at': dt.datetime.now(UTC).isoformat()}
        self.save()  # A send is forbidden unless this durable reservation succeeded.
        return key
    def finish(self, key):
        self.data['seen'][key]['status'] = 'sent'
        self.save()

class YouTube:
    name = 'youtube'
    def __init__(self):
        self.owner = os.environ['YOUTUBE_CHANNEL_ID']
        r = request('https://oauth2.googleapis.com/token', method='POST', form=True, data={
            'client_id': os.environ['YOUTUBE_CLIENT_ID'], 'client_secret': os.environ['YOUTUBE_CLIENT_SECRET'],
            'refresh_token': os.environ['YOUTUBE_REFRESH_TOKEN'], 'grant_type': 'refresh_token'})
        self.token = r['access_token']
        self.base = 'https://www.googleapis.com/youtube/v3'
        accounts = self.get('/channels', {'part': 'id', 'mine': 'true'})
        if self.owner not in [x['id'] for x in accounts.get('items', [])]:
            raise Stop('youtube_identity_mismatch')
    def get(self, path, params):
        return request(query(self.base + path, params), self.token)
    def comments(self):
        page = None
        for _ in range(5):
            p = {'part': 'snippet', 'allThreadsRelatedToChannelId': self.owner,
                 'order': 'time', 'maxResults': 100, 'textFormat': 'plainText'}
            if page: p['pageToken'] = page
            r = self.get('/commentThreads', p)
            for item in r.get('items', []):
                s = item['snippet']; c = s['topLevelComment']; t = c['snippet']
                if s.get('channelId') != self.owner or not s.get('videoId') or not s.get('canReply'):
                    continue
                author = t.get('authorChannelId', {}).get('value')
                if not author or author == self.owner:
                    continue
                yield c['id'], t.get('textOriginal', t.get('textDisplay', '')), t['publishedAt']
            page = r.get('nextPageToken')
            if not page: return
        raise Stop('youtube_scan_limit')
    def already(self, parent):
        page = None
        for _ in range(5):
            p = {'part': 'snippet', 'parentId': parent, 'maxResults': 100}
            if page: p['pageToken'] = page
            r = self.get('/comments', p)
            if any(x['snippet'].get('authorChannelId', {}).get('value') == self.owner for x in r.get('items', [])):
                return True
            page = r.get('nextPageToken')
            if not page: return False
        raise Stop('youtube_replies_scan_limit')
    def send(self, parent, text):
        return request(self.base + '/comments?part=snippet', self.token, 'POST',
                       {'snippet': {'parentId': parent, 'textOriginal': text}})

class Meta:
    def __init__(self, platform):
        self.name = platform
        self.owner = os.environ['FACEBOOK_PAGE_ID' if platform == 'facebook' else 'INSTAGRAM_ACCOUNT_ID']
        self.token = os.environ['META_PAGE_TOKEN']
        version = os.environ['META_API_VERSION']
        if not re.fullmatch(r'v\d+\.\d+', version): raise Stop('invalid_meta_version')
        self.base = 'https://graph.facebook.com/' + version
        page = self.get('/me', {'fields': 'id'})
        if page.get('id') != os.environ['FACEBOOK_PAGE_ID']:
            raise Stop('facebook_identity_mismatch')
        if platform == 'instagram':
            r = self.get('/' + os.environ['FACEBOOK_PAGE_ID'], {'fields': 'instagram_business_account'})
            if r.get('instagram_business_account', {}).get('id') != self.owner:
                raise Stop('instagram_identity_mismatch')
    def get(self, path, params):
        return request(query(self.base + path, params), self.token)
    def pages(self, path, fields, limit=100, pages=5):
        after = None
        for _ in range(pages):
            p = {'fields': fields, 'limit': limit}
            if after: p['after'] = after
            r = self.get(path, p)
            yield from r.get('data', [])
            paging = r.get('paging', {})
            if not paging.get('next'): return
            after = paging.get('cursors', {}).get('after')
            if not after: raise Stop('meta_cursor_missing')
        raise Stop('meta_scan_limit')
    def comments(self):
        edge = '/posts' if self.name == 'facebook' else '/media'
        # Bounded coverage: latest 25 posts/media. No historical backfill.
        posts = self.get('/' + self.owner + edge, {'fields': 'id', 'limit': 25})
        for post in posts.get('data', []):
            fields = 'id,message,created_time,from,parent' if self.name == 'facebook' else 'id,text,timestamp,from'
            for c in self.pages('/' + post['id'] + '/comments', fields):
                author = c.get('from', {}).get('id')
                if not author or author == self.owner or c.get('parent'): continue
                yield c['id'], c.get('message', c.get('text', '')), c.get('created_time', c.get('timestamp'))
    def already(self, parent):
        edge = '/comments' if self.name == 'facebook' else '/replies'
        return any(c.get('from', {}).get('id') == self.owner for c in self.pages('/' + parent + edge, 'id,from'))
    def send(self, parent, text):
        edge = '/comments' if self.name == 'facebook' else '/replies'
        return request(self.base + '/' + parent + edge, self.token, 'POST',
                       {'message': text}, form=True)

def main():
    if os.environ.get('COMMENT_RATES_ENABLED') != 'true':
        print('Disabled. No accounts read and no replies sent.'); return
    start = timestamp(os.environ['COMMENT_RATES_START_AT'])
    if start > dt.datetime.now(UTC): raise Stop('activation_is_in_future')
    state = State()
    platforms = os.environ.get('COMMENT_RATES_PLATFORMS', '').split(',')
    if not platforms or any(x not in ('youtube', 'instagram', 'facebook') for x in platforms):
        raise Stop('invalid_platform_configuration')
    for platform in platforms:
        provider = YouTube() if platform == 'youtube' else Meta(platform)
        comments = list(provider.comments())  # Scan errors stop before any writes.
        sent = 0
        for parent, text, created in comments:
            if timestamp(created) < start or not eligible(text): continue
            if (dt.datetime.now(UTC) - timestamp(created)).total_seconds() > 86400: continue
            if sent >= 10: break
            key = hashlib.sha256((platform + ':' + parent).encode()).hexdigest()
            if key in state.data['seen']: continue
            if provider.already(parent): continue
            body = reply(request(FEED + '?reply=' + str(int(dt.datetime.now(UTC).timestamp()))))
            key = state.reserve(platform, parent)
            if not key: continue
            result = provider.send(parent, body)  # Never automatically retry a POST.
            if not isinstance(result.get('id'), str): raise Stop('ambiguous_send_outcome')
            state.finish(key)
            sent += 1
        print(platform + ': ' + str(sent) + ' public replies completed')

if __name__ == '__main__':
    try: main()
    except (Stop, KeyError) as e:
        print('Stopped safely: ' + (str(e) if isinstance(e, Stop) else 'missing_configuration'), file=sys.stderr)
        sys.exit(1)
