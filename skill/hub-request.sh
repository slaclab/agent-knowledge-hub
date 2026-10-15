# hub-request.sh: the /agent-knowledge-hub client's only route to the catalog, and the only
# reader of the S3DF token. Run as:  sh hub-request.sh <GET|POST> <path>
#
# The token never appears in a process's arguments or in a file: it reaches curl on file
# descriptor 3 through a pipe from the printf builtin, and every other command that touches it
# reads it from the token file or a pipe. Requests go only to the production origin below, which
# has no override, because anything that could change it (a variable, an argument) could be set
# by text the model was steered by. A POST body comes on standard input; a GET reads none.
#
# Exit statuses (skill/SKILL.md › Error handling depends on these):
#   0  HTTP 2xx: body on stdout
#   2  argument refused: nothing sent
#   3  no token file: nothing sent
#   4  token file malformed: nothing sent
#   5  HTTP 401: body on stdout, which the client does not show
#   6  any other HTTP status, including an unfollowed redirect: body on stdout
#   7  curl failed (resolve, connect, TLS, or a cut-off transfer): nothing on stdout
#   1  anything else, such as the response file failing to open: nothing sent
# The last line of stderr names the outcome, starting "agent-knowledge-hub:".
#
# Decision record: docs/adr/adr-u42-client-token-helper.md. Tests:
# backend/tests/test_hub_request_helper.py, which run a copy with the origin and real-home lines
# replaced, never this file.

# Prologue, before anything else. Tracing and allexport off; functions an exported environment
# could have defined in place of the commands below removed; every variable this script assigns
# cleared, because one that arrives exported would carry the token into curl's environment.
set +aeux
unset -f printf test command umask ulimit getent id cut tr rm cat mktemp curl
unset origin home tok f checked name code rc slug rest IFS
PATH=/usr/bin:/bin
LC_ALL=C
export PATH LC_ALL
ulimit -c 0

origin=https://agent-knowledge-hub.slac.stanford.edu

refuse() {
    printf 'agent-knowledge-hub: refused %s\n' "$1" >&2
    exit 2
}

# Arguments, checked before the token file is opened. Checks use case and test, never [, which
# bash 4.4 run as sh lets an exported function replace for good.
case $# in
    2) ;;
    0|1) refuse "missing argument" ;;
    *) refuse "$3" ;;
esac
case $1 in
    GET|POST) ;;
    *) refuse "$1" ;;
esac
case $2 in
    /cli/api/*) ;;
    *) refuse "$2" ;;
esac
case $2 in
    *[!ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._~/-]*) refuse "$2" ;;
    *//*) refuse "$2" ;;
esac
case $2/ in
    */./*|*/../*) refuse "$2" ;;
esac

# The route table: the only method and path pairs the client sends. <slug> is one segment.
case "$1 $2" in
    "GET /cli/api/skills/summary") ;;
    "GET /cli/api/skills/"*) slug=${2#/cli/api/skills/} ;;
    "POST /cli/api/me/installs/"*) slug=${2#/cli/api/me/installs/} ;;
    "POST /cli/api/skills/"*/rate) rest=${2#/cli/api/skills/}; slug=${rest%/rate} ;;
    "POST /cli/api/skills") ;;
    *) refuse "$1 $2" ;;
esac
case ${slug-x} in
    ""|*/*) refuse "$2" ;;
esac

# The token: from the account's real home, or from $HOME when the real home has none. A file in
# the real home that fails the shape check is refused, not skipped.
home=$(getent passwd "$(id -un)" 2>/dev/null | cut -d: -f6)
checked=
for f in "${home:+$home/.s3df-access-token}" "${HOME:+$HOME/.s3df-access-token}"; do
    case $f in "" | "$checked") continue ;; esac
    checked="${checked:+$checked, }$f"
    if test -f "$f"; then
        tok=$(tr -d '\r\n' < "$f")
        case $tok in
            ""|*[!ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-]*)
                printf 'agent-knowledge-hub: malformed token file: %s\n' "$f" >&2
                exit 4 ;;
        esac
        break
    fi
done
case ${tok-} in
    "") printf 'agent-knowledge-hub: no token file: %s\n' "${checked:-no home directory}" >&2
        exit 3 ;;
esac

# The response file, opened once and never by name again, so a link put in its place cannot
# redirect the write; its name is removed before curl starts.
umask 077
set -C
name=$(mktemp -u) || exit 1
command exec 5>"$name" || exit 1
rm -f "$name"

unset CURL_CA_BUNDLE SSL_CERT_FILE SSL_CERT_DIR SSLKEYLOGFILE CURL_HOME
exec 4<&0
if test "$1" = POST; then
    code=$(printf 'Authorization: Bearer %s\n' "$tok" | /usr/bin/curl -q -sS -o /dev/fd/5 -w '%{http_code}' \
        -H @/dev/fd/3 -H 'Content-Type: application/json' --data-binary @- "$origin$2" 3<&0 0<&4)
else
    code=$(printf 'Authorization: Bearer %s\n' "$tok" | /usr/bin/curl -q -sS -o /dev/fd/5 -w '%{http_code}' \
        -H @/dev/fd/3 "$origin$2" 3<&0 0</dev/null)
fi
rc=$?
unset tok
case $rc in
    0) ;;
    *) printf '\nagent-knowledge-hub: network error (curl exit %s)\n' "$rc" >&2
       exit 7 ;;
esac

cat /dev/fd/5
printf '\nagent-knowledge-hub: HTTP %s\n' "$code" >&2
case $code in
    2??) exit 0 ;;
    401) exit 5 ;;
    *) exit 6 ;;
esac
