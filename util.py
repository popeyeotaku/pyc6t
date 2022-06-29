"""C6T - C version 6 by Troy - Utility Routines"""

class CompilerCrash(BaseException):
    """Indicates the compiler had a fatal crashing error."""

def error(holder, msg: str, line: int | None = None):
    """Output an error message.
    """
    if line is None:
        line = holder.curline
    print(f'{line}: {msg}')
    holder.errs += 1
