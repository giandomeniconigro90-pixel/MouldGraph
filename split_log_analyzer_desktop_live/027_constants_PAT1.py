PAT1 = re.compile(r'^\[?(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\]?\s+(ERROR|WARNING|WARN|INFO|DEBUG|TRACE|FATAL|CRITICAL)\s+\[([^\]]+)\]\s+(.*)',re.IGNORECASE)
