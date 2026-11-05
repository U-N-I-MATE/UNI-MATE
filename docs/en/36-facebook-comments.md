# 36 - Facebook Page comments

*[Tiếng Việt](../36-binh-luan-facebook.md) · **English***

From 0.448.0 UNI MATE brings **comments under your Facebook Page's posts** into the inbox, one account per Page and one conversation per post. This release is **read only**: no replies from UNI MATE yet.

## How it reads

- The Facebook app stays in **development mode**, no Meta review needed. In that mode Meta does not push customers' comments, so UNI MATE **reads every 3 minutes**.
- It reads posts from the **last 30 days** plus **followed posts** (an older post with an ad running on it: paste its link on the Page card). A newly connected Page brings the comments of the last 7 days.
- An ad run from a **published post** (Boost post, or "Use existing post" in Ads Manager) keeps its comments on that post, read like any other post.
- **No commenter names yet:** in development mode Meta hides people who have no role on the app. The inbox shows "Facebook user" with an "Open on Facebook" link. Once Meta approves Business Asset User Profile Access, new comments carry the name and comments on posts from the last 30 days are filled in.
- Each Page costs about 530 calls a day, about 11% of Meta's minimum allowance. At 80% UNI MATE slows down; when Facebook reports a limit, it waits as long as Facebook says.

## Create the Facebook app (once)

1. On developers.facebook.com, with the account that manages the Pages, create an app with the **"Manage everything on your Page"** use case. Leave it in development mode.
2. In **Use cases > Customize**, click **"Add"** for `pages_read_engagement` and `pages_read_user_content`. A new app only has `pages_show_list`; without this step Facebook cannot grant the other two.
3. In the app's Facebook Login settings, paste the **Redirect address** (shown on UNI MATE's Facebook comments card) into "Valid OAuth Redirect URIs".
4. Turn on **"Require App Secret"** in App settings > Advanced. UNI MATE signs every call with the App Secret, so a leaked access token alone is useless.

## Connect Pages in UNI MATE

1. Open UNI MATE on its **HTTPS domain** (VPS). Facebook login does not work without HTTPS.
2. **Connections > Available > Facebook comments**, click Connect. Paste the **App ID** and **App Secret** (App settings > Basic) and Save. The App Secret is encrypted and never shown again.
3. Click **Log in with Facebook**. When Facebook asks, pick the Pages to read (for example **"current Page only"**) and allow.
4. UNI MATE lists the Pages: tick them and click **Connect the ticked Pages**. Comments reach the inbox within minutes (Read now reads at once).

**Adding Pages later**: click **Add Pages**, log in again and tick the new Page. Pages already connected keep their comments; ticking one again only renews its login.

## Personal data

- Comments are kept **12 months** (1 to 24 in the settings), older ones are deleted every day.
- **Disconnect** deletes every comment, conversation and the access token of that Page (click twice; the first click says how many comments will go).
- Commenters' names show only in the inbox, never in notifications or server logs. Access tokens and the App Secret are never shown in the interface.

## When to log in again

A Page token does not expire by itself, but stops working after a Facebook password change, a removed admin role or a security check. Meta also limits data access to about 90 days. The Page card says **"Log in again"** or **"Log in again soon"** (14 days ahead): click Add Pages, log in and tick that Page again.
