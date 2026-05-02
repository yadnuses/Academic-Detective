"""Filter DeepSeek DSML thinking tokens from streaming chunks."""

# DSML blocks start with <｜｜DSML｜｜ and end with matching closing tag
# In streaming, these get split across chunks, so we need a stateful buffer.

class DSMLFilter:
    def __init__(self):
        self.buffer = ""
        self.in_dsml = False
        self.dsml_depth = 0

    def feed(self, chunk: str) -> str:
        """Feed a chunk, return clean text with DSML removed."""
        self.buffer += chunk
        result = ""
        i = 0
        while i < len(self.buffer):
            if not self.in_dsml:
                # Look for DSML start
                idx = self.buffer.find("<｜｜DSML｜｜", i)
                if idx == -1:
                    # No DSML start in remaining buffer
                    result += self.buffer[i:]
                    self.buffer = ""
                    break
                else:
                    result += self.buffer[i:idx]
                    i = idx + len("<｜｜DSML｜｜")
                    self.in_dsml = True
                    self.dsml_depth = 1
            else:
                # Inside DSML: look for nested starts or end
                start_idx = self.buffer.find("<｜｜DSML｜｜", i)
                # DSML blocks end with > followed by newline or next content
                # The simplest heuristic: find the next > that closes the current tag
                end_idx = self.buffer.find(">", i)
                if end_idx == -1:
                    # Incomplete tag, keep in buffer
                    self.buffer = self.buffer[i:]
                    break
                # Check if there's a nested DSML start before this end
                if start_idx != -1 and start_idx < end_idx:
                    self.dsml_depth += 1
                    i = start_idx + len("<｜｜DSML｜｜")
                else:
                    self.dsml_depth -= 1
                    i = end_idx + 1
                    if self.dsml_depth <= 0:
                        self.in_dsml = False
                        self.dsml_depth = 0
        return result

    def flush(self) -> str:
        """Return any remaining clean text."""
        if self.in_dsml:
            return ""
        result = self.buffer
        self.buffer = ""
        return result


def clean_dsml(text: str) -> str:
    """Non-streaming: remove all DSML blocks from complete text."""
    result = ""
    i = 0
    while i < len(text):
        start = text.find("<｜｜DSML｜｜", i)
        if start == -1:
            result += text[i:]
            break
        result += text[i:start]
        # Find end of this DSML block (next > at top level)
        depth = 1
        j = start + len("<｜｜DSML｜｜")
        while j < len(text) and depth > 0:
            if text.startswith("<｜｜DSML｜｜", j):
                depth += 1
                j += len("<｜｜DSML｜｜")
            elif text[j] == ">":
                depth -= 1
                j += 1
            else:
                j += 1
        i = j
    return result
