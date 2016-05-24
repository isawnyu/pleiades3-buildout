#!/bin/bash
set -e

for pkg in $(ls src); do
  cd src/$pkg
  echo "$pkg = git $(cat .git/config | grep url | cut -f 3 -d' ') rev=$(git rev-parse HEAD)"
  cd - > /dev/null
done
