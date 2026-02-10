# -*- coding: utf-8 -*-
from odoo import models, api, fields
import requests
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
from datetime import datetime, date
import logging

_logger = logging.getLogger(__name__)

MONTH_MAP = {
    "Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
    "Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
    "September": 9, "Oktober": 10, "November": 11, "Desember": 12,
}

class CurrencyRateScraper(models.Model):
    _inherit = "res.currency.rate"

    def _clean_number(self, raw):
        """Clean numeric string by removing Rp, spaces, thousand separators, and converting decimal commas"""
        cleaned = raw.replace("Rp", "").replace(" ", "").strip()
        cleaned = cleaned.replace(".", "").replace(",", ".")
        return float(cleaned)

    def _parse_bi_date(self, raw_date):
        """Example input: '26 Januari 2026' → datetime.date(2026, 1, 26)"""
        parts = raw_date.strip().split()
        if len(parts) == 3:
            try:
                day = int(parts[0])
                month = MONTH_MAP.get(parts[1])
                year = int(parts[2])
                if month:
                    return datetime(year, month, day).date()
            except Exception as e:
                _logger.error("Failed to parse BI date %s: %s", raw_date, e)
        return None

    def _safe_get(self, url):
        """Helper to fetch HTML with timeout and headers for stability"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
        }
        try:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            return response.text
        except RequestException as e:
            _logger.error("Failed to fetch %s: %s", url, e)
            return None
        
    @api.model
    def fetch_bi_rates(self):
        today = date.today()
        # Skip weekends
        if today.weekday() >= 5:  # 5=Saturday, 6=Sunday
            _logger.info("Skipping BI rate fetch on weekend: %s", today)
            return

        # Get active currencies except IDR
        active_currencies = self.env['res.currency'].search([('active', '=', True)])
        active_codes = [c.name for c in active_currencies if c.name != "IDR"]
        companies = self.env['res.company'].search([])

        # --- JISDOR (USD) ---
        if "USD" in active_codes:
            html = self._safe_get("https://www.bi.go.id/id/statistik/informasi-kurs/jisdor/Default.aspx")
            if html:
                soup = BeautifulSoup(html, "html.parser")
                table = soup.find("table")
                if table:
                    rows = table.find_all("tr")
                    for row in rows[1:]:
                        cols = [col.get_text(strip=True) for col in row.find_all("td")]
                        if cols and len(cols) >= 2:
                            date_obj = self._parse_bi_date(cols[0])
                            if not date_obj:
                                continue
                            try:
                                rate_value = self._clean_number(cols[1])
                            except ValueError:
                                _logger.error("Failed to parse USD rate: %s", cols[1])
                                continue

                            usd_currency = self.env.ref("base.USD", raise_if_not_found=False)
                            if not usd_currency:
                                _logger.warning("USD currency not found in Odoo")
                                break

                            for company in companies:
                                existing = self.search([
                                    ("currency_id", "=", usd_currency.id),
                                    ("name", "=", date_obj),
                                    ("company_id", "=", company.id),
                                ], limit=1)

                                if existing:
                                    existing.rate = rate_value
                                    _logger.info("Updated USD rate: %s on %s for company %s",
                                                 rate_value, date_obj, company.name)
                                else:
                                    self.create({
                                        "name": date_obj,
                                        "currency_id": usd_currency.id,
                                        "rate": rate_value,
                                        "company_id": company.id,
                                    })
                                    _logger.info("Created USD rate: %s on %s for company %s",
                                                 rate_value, date_obj, company.name)
                            break

        # --- BI Transaction Rates (non-USD) ---
        html = self._safe_get("https://www.bi.go.id/id/statistik/informasi-kurs/transaksi-bi/Default.aspx")
        if html:
            soup = BeautifulSoup(html, "html.parser")

            # Find span with class font-weight-bold containing the date
            date_span = soup.find("span", class_="font-weight-bold")
            if date_span:
                date_obj = self._parse_bi_date(date_span.get_text(strip=True))
                _logger.info("Parsed BI Transaction date: %s → %s", date_span.get_text(strip=True), date_obj)
            else:
                date_obj = date.today()
                _logger.warning("Date span not found, fallback to today: %s", date_obj)

            # Find the correct table by checking headers
            tables = soup.find_all("table")
            target_table = None
            for t in tables:
                headers = [th.get_text(strip=True) for th in t.find_all("th")]
                if "Mata Uang" in headers and "Kurs Jual" in headers:
                    target_table = t
                    break

            if target_table:
                rows = target_table.find_all("tr")
                for row in rows[1:]:
                    cols = [col.get_text(strip=True) for col in row.find_all("td")]
                    if cols and len(cols) >= 4:
                        _logger.info("Row parsed: %s", cols)

                        currency_code = cols[0]  # Currency code
                        if currency_code not in active_codes or currency_code == "USD":
                            _logger.info("Skipping %s (not active or USD)", currency_code)
                            continue

                        try:
                            sell_rate = self._clean_number(cols[2])
                            buy_rate = self._clean_number(cols[3])
                            mid_rate = (sell_rate + buy_rate) / 2.0
                            _logger.info("Currency %s: sell=%s buy=%s mid=%s", currency_code, sell_rate, buy_rate, mid_rate)
                        except ValueError:
                            _logger.error("Failed to parse %s rates: %s / %s",
                                          currency_code, cols[2], cols[3])
                            continue

                        currency = self.env.ref("base.%s" % currency_code, raise_if_not_found=False)
                        if not currency:
                            _logger.warning("Currency %s not found in Odoo", currency_code)
                            continue

                        for company in companies:
                            existing = self.search([
                                ("currency_id", "=", currency.id),
                                ("name", "=", date_obj),
                                ("company_id", "=", company.id),
                            ], limit=1)

                            if existing:
                                existing.write({ "inverse_company_rate": mid_rate}) 
                                _logger.info("Updated %s inverse company rate: %s on %s for company %s", 
                                             currency_code, mid_rate, date_obj, company.name)
                            else:
                                self.create({
                                    "name": date_obj,
                                    "currency_id": currency.id,
                                    "inverse_company_rate": mid_rate,
                                    "company_id": company.id,
                                })
                                _logger.info("Created %s inverse company rate: %s on %s for company %s",
                                             currency_code, mid_rate, date_obj, company.name)
