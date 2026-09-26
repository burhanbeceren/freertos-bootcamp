/**
 * @file msg.c
 */
#include "msg.h"

void sb_init(sb_t *sb, char *buf, size_t cap)
{
    sb->buf = buf;
    sb->cap = cap;
    sb->len = 0;
    sb->overflow = false;
}

void sb_char(sb_t *sb, char c)
{
    if (sb->len < sb->cap) {
        sb->buf[sb->len++] = c;
    } else {
        sb->overflow = true;
    }
}

void sb_str(sb_t *sb, const char *s)
{
    while (*s != '\0') {
        sb_char(sb, *s++);
    }
}

void sb_u32(sb_t *sb, uint32_t v)
{
    char tmp[10];
    int  n = 0;
    do {
        tmp[n++] = (char)('0' + (v % 10u));
        v /= 10u;
    } while (v != 0u);
    while (n > 0) {
        sb_char(sb, tmp[--n]);
    }
}

bool msg_seal_fixed(sb_t *sb)
{
    if (sb->overflow || sb->cap < MSG_LEN || sb->len > (MSG_LEN - 1u)) {
        return false;
    }
    while (sb->len < (MSG_LEN - 1u)) {
        sb->buf[sb->len++] = ' ';
    }
    sb->buf[sb->len++] = '\n';
    return true;
}

bool msg_seal_line(sb_t *sb)
{
    sb_char(sb, '\n');
    return !sb->overflow;
}
