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
    rlc
    jnc noextend
    dcr h
noextend:
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
i: .storage 1

    .text
cmult:
    .export cmult
    push b
    mov b,h
    mov l,c
    shld n
    lxi h,0 ; Don't clear DE since it will get replaced
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
    jnz multskip

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
    mov a,l
    ral
    ani $FE
    mov l,a
    mov a,h
    ral
    mov h,a
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
    jnc divskip ;??
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