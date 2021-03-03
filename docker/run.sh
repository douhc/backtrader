#!/bin/bash
docker run -it --rm --name backtrader -v ${PWD}:/opt/backtrader backtrader:v1.0.0