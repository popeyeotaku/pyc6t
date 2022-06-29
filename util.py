"""C6T - C version 6 by Troy - Utility Routines"""


def word(i: int) -> int:
    """Perform overflow and unsigning operations to get the integer into the
    same shape as an unsigned 16bit int.
    """
    if i < 0:
        i = (i ^ 0xFFFF) + 1
    return i & 0xFFFF


class CompilerCrash(BaseException):
    """Indicates the compiler had a fatal crashing error."""


def error(holder, msg: str, line: int | None = None):
    """Output an error message.
    """
    if line is None:
        line = holder.curline
    print(f'{line}: {msg}')
    holder.errs += 1
