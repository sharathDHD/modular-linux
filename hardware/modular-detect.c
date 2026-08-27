/*
 * modular-detect - minimal hardware prober for the Modular Linux live ISO.
 *
 * Reads /proc and /sys directly so the live environment does not need
 * lscpu/lsblk/rfkill/etc installed. Emits a single JSON object on stdout.
 *
 * Build: see ../Makefile   (cc -O2 -Wall -o modular-detect modular-detect.c)
 */

#include <ctype.h>
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define MAXSTR 512

static int dir_has_entry(const char *path, const char *prefix) {
    DIR *d = opendir(path);
    if (!d) return 0;
    struct dirent *e;
    int found = 0;
    while ((e = readdir(d)) != NULL) {
        if (prefix == NULL || strncmp(e->d_name, prefix, strlen(prefix)) == 0) {
            found = 1;
            break;
        }
    }
    closedir(d);
    return found;
}

static int read_first_line(const char *path, char *out, size_t n) {
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    if (fgets(out, (int)n, f) == NULL) { fclose(f); return 0; }
    size_t len = strlen(out);
    while (len > 0 && (out[len-1] == '\n' || out[len-1] == '\r' || out[len-1] == ' '))
        out[--len] = '\0';
    fclose(f);
    return 1;
}

static char *json_escape(const char *in) {
    /* Two rotating buffers so two escapes can appear in one printf. */
    static char buf[2][MAXSTR * 2];
    static int slot = 0;
    char *out = buf[slot];
    slot = (slot + 1) % 2;
    size_t j = 0;
    for (size_t i = 0; in[i] && j < MAXSTR * 2 - 2; i++) {
        unsigned char c = (unsigned char)in[i];
        if (c == '"' || c == '\\') out[j++] = '\\';
        else if (c < 0x20) continue;
        out[j++] = (char)c;
    }
    out[j] = '\0';
    return out;
}

static void print_cpu(void) {
    char line[MAXSTR], model[MAXSTR] = "", vendor[MAXSTR] = "";
    FILE *f = fopen("/proc/cpuinfo", "r");
    if (f) {
        while (fgets(line, sizeof(line), f)) {
            if (model[0] == '\0' && strncmp(line, "model name", 10) == 0) {
                char *v = strchr(line, ':');
                if (v) {
                    v++;
                    while (*v == ' ') v++;
                    v[strcspn(v, "\n")] = '\0';
                    strncpy(model, v, MAXSTR - 1);
                }
            } else if (vendor[0] == '\0' && strncmp(line, "vendor_id", 9) == 0) {
                char *v = strchr(line, ':');
                if (v) {
                    v++;
                    while (*v == ' ') v++;
                    v[strcspn(v, "\n")] = '\0';
                    strncpy(vendor, v, MAXSTR - 1);
                }
            }
        }
        fclose(f);
    }
    long cores_n = sysconf(_SC_NPROCESSORS_ONLN);
    if (cores_n < 0) cores_n = 0;
    if (model[0])
        printf("\"cpu\": {\"present\": true, \"model\": \"%s\", "
               "\"vendor\": \"%s\", \"cores\": %ld}",
               json_escape(model), json_escape(vendor), cores_n);
    else
        printf("\"cpu\": {\"present\": false, \"model\": null, "
               "\"vendor\": null, \"cores\": %ld}",
               cores_n);
}

static void print_memory(void) {
    FILE *f = fopen("/proc/meminfo", "r");
    long total_kb = -1;
    if (f) {
        char line[MAXSTR];
        while (fgets(line, sizeof(line), f)) {
            if (strncmp(line, "MemTotal:", 9) == 0) {
                sscanf(line + 9, "%ld", &total_kb);
                break;
            }
        }
        fclose(f);
    }
    if (total_kb >= 0)
        printf(", \"memory\": {\"total_mb\": %ld}", total_kb / 1024);
    else
        printf(", \"memory\": {\"total_mb\": null}");
}

static void print_gpu(void) {
    printf(", \"gpu\": [");
    DIR *d = opendir("/sys/class/drm");
    int first = 1;
    if (d) {
        struct dirent *e;
        while ((e = readdir(d)) != NULL) {
            if (strncmp(e->d_name, "card", 4) == 0 &&
                isdigit((unsigned char)e->d_name[4]) &&
                strchr(e->d_name, '-') == NULL) {
                char path[MAXSTR], dev[MAXSTR] = "";
                snprintf(path, sizeof(path), "/sys/class/drm/%s/device/vendor",
                         e->d_name);
                read_first_line(path, dev, sizeof(dev));
                const char *name = "unknown";
                if (strncmp(dev, "0x8086", 6) == 0) name = "intel";
                else if (strncmp(dev, "0x1002", 6) == 0 ||
                         strncmp(dev, "0x1022", 6) == 0) name = "amd";
                else if (strncmp(dev, "0x10de", 6) == 0) name = "nvidia";
                printf("%s{\"id\": \"%s\", \"vendor\": \"%s\"}",
                       first ? "" : ", ", e->d_name, name);
                first = 0;
            }
        }
        closedir(d);
    }
    printf("]");
}

static void print_storage(void) {
    printf(", \"storage\": [");
    DIR *d = opendir("/sys/block");
    int first = 1;
    if (d) {
        struct dirent *e;
        while ((e = readdir(d)) != NULL) {
            if (e->d_name[0] == '.') continue;
            if (strncmp(e->d_name, "loop", 4) == 0 ||
                strncmp(e->d_name, "ram", 3) == 0 ||
                strncmp(e->d_name, "zram", 4) == 0 ||
                strncmp(e->d_name, "sr", 2) == 0)
                continue;
            char path[MAXSTR], val[MAXSTR];
            unsigned long long sectors = 0;
            snprintf(path, sizeof(path), "/sys/block/%s/size", e->d_name);
            if (read_first_line(path, val, sizeof(val)))
                sectors = strtoull(val, NULL, 10);
            unsigned long long gb = sectors * 512ULL / (1000ULL * 1000 * 1000);
            snprintf(path, sizeof(path), "/sys/block/%s/device/model",
                     e->d_name);
            char model[MAXSTR] = "";
            read_first_line(path, model, sizeof(model));
            printf("%s{\"name\": \"%s\", \"size_gb\": %llu, \"model\": \"%s\"}",
                   first ? "" : ", ", e->d_name, gb, json_escape(model));
            first = 0;
        }
        closedir(d);
    }
    printf("]");
}

static void print_network(void) {
    int wired = 0, wireless = 0;
    DIR *d = opendir("/sys/class/net");
    if (d) {
        struct dirent *e;
        while ((e = readdir(d)) != NULL) {
            if (strcmp(e->d_name, "lo") == 0 || e->d_name[0] == '.')
                continue;
            char path[MAXSTR];
            snprintf(path, sizeof(path), "/sys/class/net/%s/wireless",
                     e->d_name);
            struct stat st;
            if (stat(path, &st) == 0 || strstr(e->d_name, "wl") == e->d_name)
                wireless = 1;
            else if (strstr(e->d_name, "en") == e->d_name ||
                     strstr(e->d_name, "eth") == e->d_name)
                wired = 1;
        }
        closedir(d);
    }
    printf(", \"network\": {\"ethernet\": %s, \"wifi\": %s}",
           wired ? "true" : "false", wireless ? "true" : "false");
}

int main(void) {
    printf("{");
    print_cpu();
    print_memory();
    print_gpu();
    print_storage();
    print_network();

    int bt = dir_has_entry("/sys/class/bluetooth", "hci");
    printf(", \"bluetooth\": %s", bt ? "true" : "false");

    int audio = dir_has_entry("/proc/asound", "card");
    printf(", \"audio\": %s", audio ? "true" : "false");

    int webcam = dir_has_entry("/sys/class/video4linux", "video");
    printf(", \"webcam\": %s", webcam ? "true" : "false");

    int touchpad = 0;
    FILE *f = fopen("/proc/bus/input/devices", "r");
    if (f) {
        char line[MAXSTR];
        while (fgets(line, sizeof(line), f)) {
            if (strstr(line, "Touchpad") || strstr(line, "touchpad")) {
                touchpad = 1;
                break;
            }
        }
        fclose(f);
    }
    printf(", \"touchpad\": %s}\n", touchpad ? "true" : "false");
    return 0;
}
