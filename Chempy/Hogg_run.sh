#!/bin/bash
for INDEX in {0..1}
do
	echo "Running python for beta index $INDEX"
	python Chempy/Hogg_trial.py $INDEX
done