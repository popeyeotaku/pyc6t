; C6T 8080 Support Code

.bss
reg0: .storage 2
reg1: .storage 2
reg2: .storage 2
.export reg0, reg1, reg2


.data
argv:
    .word name

name:
    .byte 'c', '6', 't', '8', '0', '8', '0', 0

argc = 1

STKSTART = $FF00

.text
start:
    .export start
    lxi sp,STKSTART
    lxi h,argv
    push h
    lxi h,argc
    push h
    call _main
_exit:
    .export _exit
    hlt
    jmp _exit

csave:
    .export csave
    pop d
    push b
    lhld reg0
    push h
    lhld reg1
    push h
    lhld reg2
    push h
    lxi h,0
    dad sp
    mov c,l
    mov b,h
    xchg
    pchl

cret:
    .export cret
    mov l,c
    mov h,b
    sphl
    pop h
    shld reg2
    pop h
    shld reg1
    pop h
    shld reg0
    pop b
    ret


ccall:
    .export ccall
    pop d
    pchl
    
cextend:
    .export cextend
    mvi h,0
    mov a,l
    ora a
    rp
    dcr h
    ret

_in80:
    .export _in80
    lxi h,2
    dad sp
    mov a,m
    sta inrel+1
inrel:
    in 0
    mov l,a
    call cextend
    ret

_out80:
    .export _out80
    lxi h,2
    dad sp
    mov a,m
    sta outrel+1
    lxi h,4
    dad sp
    mov a,m
outrel:
    out 0
    ret

    .bss
n: .storage 2
i: .storage 2

    .text
cmult:
    .export cmult
    push b
    mov b,d
    mov c,e
    shld n
    lxi h,0
    lxi d,0
    mvi a,16
    sta i
multloop:
    lda n+1
    rar
    ani $7F
    sta n+1
    lda n
    rar
    sta n
    jnc multskip
    dad b
multskip:
    mov a,h
    rar
    ani $7F
    mov h,a
    mov a,l
    rar
    mov l,a
    mov a,d
    rar
    mov d,a
    mov a,e
    rar
    mov e,a
    lda i
    dcr a
    sta i
    jnz multloop

    ; Result in DE
    xchg
    pop b
    ret

cdiv:
    .export cdiv
    push b
    call div
    pop b
    ret

div:
    ; HL = dividend/result,
    ; DE = divisor,cdiv
    ; BC = remainder
    .export div
    lxi b,0
    mvi a,16
    sta i
divloop:
    ; shift dividend left into remainder
    mov a,h ; high bit of HL into carry
    rlc
    dad h
    mov a,c
    ral
    mov c,a
    mov a,b
    ral
    mov b,a
    ; If remainder - divisor doesn't overflow, result is new remainder and inc result
    mov a,c
    sub e
    sta n
    mov a,b
    sbb d
    sta n+1
    jc divskip ;branches if overflow
    lda n
    mov c,a
    lda n+1
    mov b,a
    inx h
divskip:
    lda i
    dcr a
    sta i
    jnz divloop
    ; Result in HL, remainder in BC
    ret


cmod:
    .export cmod
    push b
    call div
    mov h,b
    mov l,c
    pop b
    ret

doswitch:
    .export doswitch
    ; on stack, from bottom to top:
    ; - return address (but we never return)
    ; - number of cases
    ; - default addr
    ; - table addr
    ; - expression value

    ; table format:
    ; - two word entries, first is value, second is addr

    ; Need to preserve BC, DE and HL don't matter
    pop h ; destroy return address

    pop h ; number of cases to I
    shld i
    pop h ; default to N
    shld n
    pop h ; table addr to HL
    pop d ; expr value to DE
    lda i+1
swloop:
    ora a
    jnz swcont
    lda i
    ora a
    jnz swcont
    ; not found, go to default
    lhld n
    pchl
swcont:
    mov a,m
    inx h
    cmp e
    jnz swbad
    mov a,m
    cmp d
    jnz swbad
    ; Found good!
    inx h ; to target addr
    mov a,m
    inx h
    mov h,m
    mov l,a
    pchl ; Jump!
swbad:
    ; HL at last byte of table value
    inx h ; targetlo
    inx h ; targethi
    inx h ; next value
    lda i
    sui 1
    sta i
    lda i+1
    sbi 0
    sta i+1
    jmp swloop

crshift:
    .export crshift
    ; Shift HL right DE bits, sign extended
    mov a,h
    ora a
    jp rplus
rminus: ; Place 1 bit in all high bits
    mov a,e
    ora d
    rz
    mov a,h
    stc
    rar
    mov h,a
    mov a,l
    rar
    mov l,a
    dcx d
    jmp rminus
rplus: ; Place 0 bit in all high bits
    mov a,e
    ora d
    rz
    stc
    cmc
    mov a,h
    rar
    mov h,a
    mov a,l
    rar
    mov l,a
    dcx d
    jmp rplus

cless:
    mov a,h
    xra d
    jp same1
    xra h
    jm gequ1
less1:
    lxi h,1
    ret
same1:
    mov a,l
    sub e
    mov a,h
    sbb d
    jc less1
gequ1:
    lxi h,0
    ret

cgequ:
    mov a,h
    xra d
    jp same2
    xra h
    jm gequ2
less2:
    lxi h,0
    ret
same2:
    mov a,l
    sub e
    mov a,h
    sbb d
    jc less2
gequ2:
    lxi h,0
    ret

clequ:
    mov a,h
    xra d
    jp same3
    xra h
    jm gequ3
less3:
    lxi h,1
    ret
same3:
    mov a,l
    sub e
    mov a,h
    sbb d
    jc less3
gequ3:
    jz less3
    lxi h,0
    ret

cgreat:
    mov a,h
    xra d
    jp same4
    xra h
    jm gequ4
less4:
    lxi h,0
    ret
same4:
    mov a,l
    sub e
    mov a,h
    sbb d
    jc less4
gequ4:
    jz less4
    lxi h,1
    ret

    .export cless, cgreat, clequ, cgequ