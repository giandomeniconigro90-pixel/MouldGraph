PAT_S= re.compile(r'^(\d{2}[./]\d{2}[./]\d{4}\s+\d{2}:\d{2}:\d{2})\s*[|;,]\s*(ERROR|ALARM|ALARM_URGENT|WARNING|WARN|INFO|DEBUG|OK)\s*[|;,]\s*([^|;,]*)[|;,]?\s*(.*)',re.IGNORECASE)
