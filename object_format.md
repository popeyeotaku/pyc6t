# C6T OBJECT FORMAT

The C6T Object Files (a.out style) consist of a header, followed by a series of segment records, followed by a symbol table.

## Endianess

Everything's little endian, babes.

## Header

- *Bytes 0-1*: size of text segment
- *Bytes 2-3*: size of data segment
- *Bytes 4-5*: size of bss segment

## Segments

Only the Text and Data segments are defined, and they both follow the same format:

An initial length byte, taken as a 2's complement signed number.

- *If positive*, the next length bytes (up to 127) are copied to output.
- *If negative*, we have a 'REFERENCE' which is treated as below.
- *If zero*, it is the end of the segment.
  
### Reference

A segment reference record takes the negation of its length byte as various flags.

- *Bit 0*: set if one byte, clear if two bytes
- *Bit 1*: set if hibyte, clear if lobyte
- *Bit 2*: set if symbol table refernce, clear if integer only
- *Bit 3*: set if bit1 should be used, clear if bit1 should be ignored
- *Bits 4-6*: reserved for future use.

If bit2 is set, the following 8 bytes are used as a null-filled symbol name, followed by a 2byte offset integer.

If bit2 is clear, the following 2 bytes are a constant integer.

If bit0 is clear, the resulting value is stored as an integer here - if set, it is stored as a single byte.

If bit3 is set, the value of bit1 is used as follows:

- If bit0 is clear for word, then a hibyte (set bit1) specifies the result should be shifted left 8 bits and the high byte cleared -- while lobyte (clear bit 1) indicates we should clear out the high byte and leave the low as it is.
- If bit1 is set for byte, then the corresponding byte of the result (low or high) is stored according to bit 1.

If relocation is requested with a symbol, the symbol is looked up in either the local symbol table or the exported symbols seen by the linker, and the result added to the integer.

If relocation is requested without a symbol, just an integer, that integer is added to the offset from the start of the current segment by the linker in the final object file.

## Symbol table

Following the text and data segments are a symbol table.

Each entry consists of an 8 byte null-filled symbol name, followed by its two byte value, and one byte of flags, for a total of 11 bytes.

A leading name byte of 0 marks the end of the symbol table.

The flags are as follows:

- *Bit 0*: set if external, clear if internal. If external, the value should be ignored.
- *Bits 0-1*: indicates text, data, or bss segments if values are 0, 1, or 2 respectively. Value 4 is currently reserved.
