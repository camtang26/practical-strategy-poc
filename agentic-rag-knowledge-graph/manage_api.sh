#!/bin/bash

case "$1" in
  start)
    echo "Starting API with Jina embeddings..."
    nohup python3 start_api.py > api.log 2>&1 &
    echo $! > api.pid
    echo "API started with PID: $(cat api.pid)"
    ;;
  stop)
    if [ -f api.pid ]; then
      kill $(cat api.pid) 2>/dev/null
      rm api.pid
      echo "API stopped"
    else
      echo "API not running"
    fi
    ;;
  restart)
    $0 stop
    sleep 2
    $0 start
    ;;
  status)
    if [ -f api.pid ] && ps -p $(cat api.pid) > /dev/null; then
      echo "API is running (PID: $(cat api.pid))"
      curl -s http://localhost:8058/health | python3 -m json.tool
    else
      echo "API is not running"
    fi
    ;;
  logs)
    tail -f api.log
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs}"
    exit 1
    ;;
esac
