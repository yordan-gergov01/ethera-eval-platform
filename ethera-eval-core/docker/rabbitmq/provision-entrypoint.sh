#!/bin/sh
# Renders the broker definitions (vhost, users, permissions) from environment
# variables into a tmpfs, then hands over to the image's own entrypoint.
#
# Compose invokes this script through `sh`, so it does not depend on the
# executable bit. Passwords exist only in the environment and in the tmpfs,
# never in the repository or the image.
#
# Permissions follow the message topology: each service may consume only from its
# own queues and publish only to the exchange. Declaring a queue needs configure on
# it, binding it needs write on the queue and read on the exchange. The backend also
# declares the job queue and the runner the result queue (configure and write,
# never read), so a message published before its consumer first starts, or while it
# is down, is kept instead of dropped. Regexes use [.] for a
# literal dot so the JSON needs no escaping.
#
# Dead-lettering and the delivery limit of the two work queues are policies here,
# not queue arguments: declaring a queue with dead-letter arguments would need read
# permission on it. common_lib/messaging/topology.py names the same values, and a
# unit test keeps the two in step.
set -eu

# Values are written into JSON strings verbatim, so anything that would need
# escaping (double quote, backslash, control characters) is rejected here with
# a clear message instead of producing a broken or altered definitions file.
require() {
    eval "value=\${$1:-}"
    if [ -z "$value" ]; then
        echo "error: environment variable $1 must be set" >&2
        exit 1
    fi
    case "$value" in
        *'"'* | *'\'* | *[[:cntrl:]]*)
            echo "error: environment variable $1 contains a character that cannot be" \
                "used safely (double quote, backslash or a control character)." \
                "Choose a value without it." >&2
            exit 1
            ;;
    esac
}

for name in RABBITMQ_VHOST \
    RABBITMQ_BACKEND_USER RABBITMQ_BACKEND_PASSWORD \
    RABBITMQ_RUNNER_USER RABBITMQ_RUNNER_PASSWORD \
    RABBITMQ_INSPECTOR_USER RABBITMQ_INSPECTOR_PASSWORD; do
    require "$name"
done

definitions_dir=/run/rabbitmq-definitions
definitions_file="$definitions_dir/definitions.json"

umask 077
cat > "$definitions_file" <<EOF
{
  "vhosts": [{"name": "$RABBITMQ_VHOST"}],
  "users": [
    {"name": "$RABBITMQ_BACKEND_USER", "password": "$RABBITMQ_BACKEND_PASSWORD", "tags": []},
    {"name": "$RABBITMQ_RUNNER_USER", "password": "$RABBITMQ_RUNNER_PASSWORD", "tags": []},
    {"name": "$RABBITMQ_INSPECTOR_USER", "password": "$RABBITMQ_INSPECTOR_PASSWORD", "tags": ["management"]}
  ],
  "permissions": [
    {
      "user": "$RABBITMQ_BACKEND_USER",
      "vhost": "$RABBITMQ_VHOST",
      "configure": "^(evals|evals[.]dlx|runner[.]jobs|runner[.]jobs[.]dlq|backend[.]runner[.]results|backend[.]runner[.]results[.]dlq)$",
      "write": "^(evals|evals[.]dlx|runner[.]jobs|runner[.]jobs[.]dlq|backend[.]runner[.]results|backend[.]runner[.]results[.]dlq)$",
      "read": "^(evals|evals[.]dlx|backend[.]runner[.]results|runner[.]jobs[.]dlq)$"
    },
    {
      "user": "$RABBITMQ_RUNNER_USER",
      "vhost": "$RABBITMQ_VHOST",
      "configure": "^(evals|evals[.]dlx|runner[.]jobs|runner[.]jobs[.]dlq|backend[.]runner[.]results|backend[.]runner[.]results[.]dlq)$",
      "write": "^(evals|evals[.]dlx|runner[.]jobs|runner[.]jobs[.]dlq|backend[.]runner[.]results|backend[.]runner[.]results[.]dlq)$",
      "read": "^(evals|evals[.]dlx|runner[.]jobs)$"
    },
    {
      "user": "$RABBITMQ_INSPECTOR_USER",
      "vhost": "$RABBITMQ_VHOST",
      "configure": "^$",
      "write": "^$",
      "read": "^(runner[.]jobs[.]dlq|backend[.]runner[.]results[.]dlq)$"
    }
  ],
  "policies": [
    {
      "vhost": "$RABBITMQ_VHOST",
      "name": "runner-jobs",
      "pattern": "^runner[.]jobs$",
      "apply-to": "queues",
      "priority": 0,
      "definition": {
        "dead-letter-exchange": "evals.dlx",
        "dead-letter-routing-key": "trial_batch.requested",
        "delivery-limit": 3
      }
    },
    {
      "vhost": "$RABBITMQ_VHOST",
      "name": "backend-runner-results",
      "pattern": "^backend[.]runner[.]results$",
      "apply-to": "queues",
      "priority": 0,
      "definition": {
        "dead-letter-exchange": "evals.dlx",
        "dead-letter-routing-key": "trial_batch.completed",
        "delivery-limit": 3
      }
    }
  ]
}
EOF
chown rabbitmq:rabbitmq "$definitions_file"

# The image links root's Erlang cookie to the broker's. The container health check
# runs rabbitmq-diagnostics as root; if it ran before the broker had created the
# cookie, it would create it owned by root, and the broker could not read it and
# would exit. Creating it here, owned by the broker's user, closes that race.
cookie=/var/lib/rabbitmq/.erlang.cookie
if [ ! -f "$cookie" ]; then
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$cookie"
    chown rabbitmq:rabbitmq "$cookie"
    chmod 400 "$cookie"
fi

exec docker-entrypoint.sh "$@"
