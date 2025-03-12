# Google Chat Incoming Webhooks

## Send Messages Using Incoming Webhooks

### Documentation
Refer to the official documentation: [Google Chat Webhooks](https://developers.google.com/chat/how-tos/webhooks).

### Setup & Usage

#### 1. Configure Webhook URL
Navigate to:
**Settings → Technical → System Parameters**
- **Name**: `google_chat_webhook_url`
- **Value**: `https://chat.googleapis.com/v1/spaces/`

#### 2. Assign Role Access
- **Role Access** → *Google Chat*

#### 3. Configure Google Chat Settings
Navigate to:
**Settings → Google Chat**

##### Example Configuration
- **Name**: Order Notifications
- **Space Code**: `AAAAXXXX`
- **Environment**: `STAGING` / `PRODUCTION`
- **Space Key**: `AIzaSyZtE6vySjXXXXXXX`
- **Space Token**: `BQvpPC3M5qppMyDcsiXXXXXX`
- **Mention Users**: `<users/123456789012345678901>`

### Example API Call (cURL)
```sh
curl -H 'Content-Type: application/json' -X POST \
"https://chat.googleapis.com/v1/spaces/AAAAXXXX/messages?key=AIzaSyZtE6vySjXXXXXXX&token=UBQJ-BQvpPC3M5qppMyDcsiXXXXXX" \
--data '{"text": "hi there"}'
```

---

## Odoo Integration Example

```python
"""
Example: Sending a webhook message to Google Chat when a sales order is confirmed.
"""
import logging
from odoo import models, _

_logger = logging.getLogger(__name__)

class SalesOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        result = super(SalesOrder, self).action_confirm()
        try:
            google_chat = self.env["google.chat"].search([( "name", "=", "Order Notifications")], limit=1)
            if google_chat:
                message = f"Sale Order {self.name} has been confirmed."
                google_chat.send_message(message)
            else:
                _logger.warning(_("Google Chat configuration not found."))
        except Exception as e:
            _logger.warning(_("Failed to send message to Google Chat: %s"), str(e))

        return result
```