# Sonar Katta public rates replies

Status: prepared, disabled. No schedule and no credentials are included. This is not a live service yet.

## Behavior

- One PUBLIC reply to new top-level rate requests only. No DMs, app links, external source names or old-comment backfill.
- Marathi rates, nearest ₹100, 24K/22K per 10g, silver 999 per kg, GST extra, and the approved social CTA.
- Feed headline fields are already non-GST. Do NOT divide them by 1.03.
- Show the feed's timestamp in IST, never pretend it is the comment's timestamp.
- Stop when data is older than 10 minutes, future-dated, mixed-time, invalid or internally inconsistent. Scheduled jobs have no instant-delivery guarantee.
- Complaints containing fake/fraud/spam/scam/wrong or Marathi equivalents are skipped. Keyword matching is deliberately limited, not an intent classifier.
- YouTube reads at most five pages of threads. Facebook/Instagram cover the latest 25 posts/media, not the entire archive. Full comment scans are bounded and fail closed on overflow.
- No automatic POST retry. Hash-only reservations are persisted to a separate `comment-rates-state` branch BEFORE sending. Failed or ambiguous sends remain reserved and need manual investigation. This prefers a missed reply over a duplicate. It is not transactional exactly-once delivery.
- Owner replies, replies to replies, comments before the activation time and comments older than one day are skipped.
- Rolling 24-hour caps: 80 YouTube attempts and 100 attempts per Meta platform; maximum 10 successful replies per platform per run. Quota/rate limits can still stop a run.
- Tokens stay in repository secrets, never source files or logs. The state branch contains hashes, timestamps, statuses and counters only. Never put comments, user identifiers or tokens into it.

## Before activation

1. Review exact output and rate-request keyword rule with Tejas. No final wording or trigger is deemed approved by this README.
2. Sign into the confirmed Google account using the secure credential flow. Enable YouTube Data API in the existing Google Cloud project after verifying ownership.
3. Create a dedicated OAuth client with a real controlled redirect/callback and request only `https://www.googleapis.com/auth/youtube.force-ssl` with offline access. The existing Firebase sign-in client is not automatically a YouTube authorization. No authorization URL can be supplied before a real client/redirect exists.
4. Store `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` in GitHub Actions secrets, securely. Never paste tokens into a chat or public issue. Google external apps in Testing lose refresh tokens after seven days for this scope; settle production/verification requirements before calling this unattended.
5. Confirm YouTube channel ID belongs to @sonarkatta. Set repository variable `YOUTUBE_CHANNEL_ID` to the verified ID.
6. Configure a Meta developer app and Facebook Login path for Tejas's own Page/linked Instagram Creator account. Verify actual permissions and access levels in the dashboard. Instagram: `instagram_basic`, `instagram_manage_comments`, `pages_read_engagement` (additional ads scopes can apply to Business Manager roles). Facebook comment replies require `pages_manage_engagement`, `pages_read_engagement` and `pages_read_user_engagement`, with task and app-access requirements verified in the dashboard. Validate all reads and one reviewed public reply before activation. Standard Access on owned/managed accounts does not mean setup-free operation.
7. Store Page token as `META_PAGE_TOKEN`. Set verified `FACEBOOK_PAGE_ID`, `INSTAGRAM_ACCOUNT_ID` and supported `META_API_VERSION`. The implementation validates Page token identity and Page-to-Instagram linkage. Token expiry, revoked permissions and removed app roles stop operation.
8. Set `COMMENT_RATES_START_AT` to a reviewed UTC ISO timestamp. Set `COMMENT_RATES_PLATFORMS` only to platforms individually tested and approved, comma-separated.
9. Keep `COMMENT_RATES_ENABLED` absent/false until the final review and live test are complete. Manual workflow initially only runs offline tests.
10. After approval, set enabled=true, then add an off-hour scheduled trigger (for example every ten minutes) to the workflow. Use standard Ubuntu runner in this public repo. GitHub scheduling may delay/drop jobs; public schedules can disable after 60 days without repository activity. Check Actions failure notifications and schedule health. There is no durable external operations monitor yet.

## Run offline tests

`python3 -m unittest discover -s automation/comment_rates -p 'test_*.py'`

## Verified implementation references

- https://developers.google.com/youtube/v3/docs/comments/insert
- https://developers.google.com/youtube/v3/docs/commentThreads/list
- https://developers.google.com/identity/protocols/oauth2
- https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits
- https://developers.facebook.com/docs/instagram-platform/comment-moderation
- https://developers.facebook.com/documentation/pages-api/comments-mentions
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions
