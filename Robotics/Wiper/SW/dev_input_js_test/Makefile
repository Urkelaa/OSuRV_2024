

#CPPFLAGS=$(shell pkg-config --cflags sdl2)
#LDFLAGS=$(shell pkg-config --libs sdl2)

run: main.elf
	./main.elf

main.elf: main.o
	${CC} -o $@ $< ${LDFLAGS} ${LIBS}