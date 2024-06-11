#!/bin/bash

largo=20
cantidad=1

tr -dc '[:alnum:]@./' < /dev/random | fold -w$largo | head -n$cantidad
