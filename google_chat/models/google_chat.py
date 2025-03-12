# -*- coding: utf-8 -*-
import logging
import requests
from odoo import models, fields

_logger = logging.getLogger(__name__)

class GoogleChatIntegration(models.Model):
    _name = "google.chat"
    _inherit = ['mail.thread']
    _description = "Google Chat Webhook Integration"

    name = fields.Char(required=True, tracking=True, help="Space Name")
    code = fields.Char(required=True, tracking=True, help="Space Code")
    title = fields.Char(required=True, tracking=True, help="STAGING or PRODUCTION.")
    key = fields.Char(required=True, tracking=True, help="Space Key")
    token = fields.Char(required=True, tracking=True, help="Space Token")
    mention = fields.Char(tracking=True, help="Mention a user, e.g., <users/123456789012345678901>")

    def send_message(self, message, thread_key=None):
        """Send a message to Google Chat using webhooks."""
        webhook_url = self.env['ir.config_parameter'].sudo().get_param('google_chat_webhook_url')
        if not webhook_url:
            _logger.warning("Google Chat webhook URL is not set.")
            return False

        responses = []
        for record in self:
            try:
                url = f"{webhook_url}{record.code}/messages?key={record.key}&token={record.token}"
                payload = {"text": f"{message}\n{record.mention or ''}"}

                if thread_key:
                    url += "&messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"
                    payload["thread"] = {"name": f"spaces/{record.code}/threads/{thread_key}"}

                response = requests.post(url, headers={'Content-Type': 'application/json'}, json=payload)
                
                if response.ok:
                    _logger.info("Message sent to Google Chat.")
                    responses.append(response.json())
                else:
                    _logger.warning(f"Failed to send message. Status: {response.status_code}, Response: {response.text}")
            
            except Exception as e:
                _logger.error(f"Error sending message to Google Chat: {e}")

        return responses