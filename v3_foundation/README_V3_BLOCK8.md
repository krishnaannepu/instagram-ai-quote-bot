# V3 Block 8 — Instagram Channel Adapter

Block 8 adds the Meta/Instagram boundary without putting quote logic back into
the webhook.

## Flow

```text
Meta webhook payload
    ↓
MetaWebhookParserV3
    ↓
sender session repository
    ↓
LocalConversationRuntimeV3
    ↓
RenderedMessage
    ↓
InstagramSender adapter
```

## New files

- `meta_webhook_parser_v3.py`
- `session_repository_v3.py`
- `instagram_sender_v3.py`
- `instagram_channel_adapter_v3.py`
- `v3_runtime_factory.py`
- `test_instagram_channel_v3.py`

Block 8 also updates `event_normalizer.py` so these customer buttons are first
class V3 events:

```text
KEEP_CURRENT_PACKAGE
SWITCH_PACKAGE_BASIC
SWITCH_PACKAGE_PREMIUM
```

## Important

Do NOT modify `main.py` yet.

Block 8 proves the webhook/channel layer in isolation with fake Instagram
delivery.

Run:

```powershell
python -m py_compile event_normalizer.py meta_webhook_parser_v3.py session_repository_v3.py instagram_sender_v3.py instagram_channel_adapter_v3.py v3_runtime_factory.py test_instagram_channel_v3.py
python test_instagram_channel_v3.py
```

Expected:

```text
V3 BLOCK 8 INSTAGRAM CHANNEL ADAPTER TEST PASSED
```

Only after this passes locally should `main.py` be changed to delegate incoming
webhook payloads to `InstagramChannelAdapterV3`.
