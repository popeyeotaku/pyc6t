; C6T 8080 Support Code

STKSTART = $FF00

.text
start:
    .export start
    lxi sp,STKSTART
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

    .bss
    .common reg0, 2
    .common reg1, 2
    .common reg2, 2
    .export reg0, reg1, reg2

    .text
    
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


cmult:
    .export cmult
    hlt
