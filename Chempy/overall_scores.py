def overall_Bayes():
	"""
	Convenience function to calculate the overall Bayes score, marginalizing over all parameters including beta.
	NB: in parameter.py, we must set the beta_parameter prior. 5+-2.5 is used here in linear space.
	"""
	import numpy as np
	import os
	from .parameter import ModelParameters
	from .score_function import Bayes_score
	
	directory = 'OverallScores/'
	if not os.path.exists(directory):
		os.makedirs(directory)
		
	a = ModelParameters()
	integral,integral_err = Bayes_score()
	
	np.savez("OverallScores/Bayes_score - "+str(a.yield_table_name_sn2)+", "+str(a.yield_table_name_agb)+", "+str(a.yield_table_name_1a)+".npz",
				score=integral,
				score_err=integral_err)
	
	return integral,integral_err
	
def overall_Hogg():
	"""
	Convenience function to calculate overall Hogg score, running MCMC over all parameters including beta.
	NB: must set beta_param / log10_beta priors in parameter file
	"""
	import numpy as np
	from Chempy.parameter import ModelParameters
	import importlib
	import fileinput
	import sys   
	import os
	import multiprocessing as mp
	import tqdm
	from Chempy.wrapper import single_star_optimization
	from Chempy.plot_mcmc import restructure_chain
	from Chempy.cem_function import posterior_function_mcmc_quick
	from scipy.stats import norm
	from .score_function import preload_params_mcmc
	import matplotlib.pyplot as plt
	#p = mp.Pool()
	
	directory = 'OverallScores/'
	if not os.path.exists(directory):
		os.makedirs(directory)
	 
	## Code to rewrite parameter file for each element in turn, so as to run MCMC for 21/22 elements only
	# This is definitely not a good implementation (involves rewriting entire parameter file),
	# But other steps are far slower
	
	# Initialise arrays
	element_mean = []
	element_sigma = []
	overall_score = 1.
	factors = []
	
	# Starting elements (copied from original parameter file)
	b = ModelParameters()
	starting_el = b.elements_to_trace
	orig = "\telements_to_trace = "+str(starting_el) # Original element string
	#print(starting_el)

	# Calculate required Chempy elements
	preload = preload_params_mcmc()
	elements_init = np.copy(preload.elements)
	np.save('Scores/Hogg_elements.npy',elements_init)
	#print(elements_init) 
   
	# Create new parameter names
	newstr = []
	for i,el in enumerate(elements_init):
		if el !='Zn':
			newstr.append(orig.replace("'"+str(el)+"', ",""))
		else:
			newstr.append(orig.replace("'"+str(el)+"'",""))
	for index in range(len(elements_init)): # Iterate over removed element
		for line in fileinput.input("Chempy/parameter.py", inplace=True):
			if "\telements_to_trace" in line:
				print(newstr[index])
				#print(line,end='') # TO TEST
			else:
				print(line,end='')
		fileinput.close()
		del sys.modules['Chempy.parameter']
		del sys.modules['Chempy.score_function']
		from Chempy.parameter import ModelParameters
		from .score_function import preload_params_mcmc 
		a = ModelParameters()
		preload = preload_params_mcmc()
		##############
		
		# Run MCMC with 27/28 elements. 
		print('Running MCMC iteration %d of %d' %(index+1,len(elements_init)))
		#print(a.elements_to_trace)
		single_star_optimization()
		
		# Create the posterior PDF and load it 
		restructure_chain('mcmc/')
		positions = np.load('mcmc/posteriorPDF.npy') # Posterior parameter PDF
		#print("In Hogg_score, element list is",a.elements_to_trace)
		
		##############
		
		for line in fileinput.input("Chempy/parameter.py", inplace=True):
			if "\telements_to_trace" in line:
				print(orig)
			else:
				print(line,end='')
		fileinput.close()
		del sys.modules['Chempy.parameter']
		del sys.modules['Chempy.score_function']
		from Chempy.parameter import ModelParameters
		from .score_function import preload_params_mcmc 
		a = ModelParameters()
		preload = preload_params_mcmc()	
		##############
		
		# This uses all 28 elements again for predictions
				
		# Multiprocess and calculate elemental predictions for each parameter set

		from .score_function import element_predictor
		p = mp.Pool()		
		indices = np.ones(len(positions))*index
		abundance = list(tqdm.tqdm(p.imap_unordered(element_predictor,zip(positions,indices)),total=len(positions)))
		p.close()
		p.join()	
		
		abundance = np.array(abundance)
		mean,sigma = norm.fit(abundance)
		print(mean)
		print(sigma)
		
		element_mean.append(mean)
		element_sigma.append(sigma)
		#a.plot_hist=True
		if a.plot_hist == True:
			plt.clf()
			plt.hist(abundance, bins=40, normed=True, alpha=0.6, color='g')
			#abundance = np.array(abundance) # Unmask array
			# Plot the PDF.
			xmin, xmax = plt.xlim()
			x = np.linspace(xmin, xmax, 100)
			p = norm.pdf(x, mean, sigma)
			plt.plot(x, p, c='k', linewidth=2)
			title = 'Plot of element %d abundance' %(index)
			plt.title(title)
			plt.xlabel('[X/Fe] abundance')
			plt.ylabel('Relative frequency')
		
		total_err = np.sqrt((preload.star_error_list[index])**2 + sigma**2)
		likelihood_factor = norm.pdf(mean,loc=preload.star_abundance_list[index],scale=total_err)
		overall_score *= likelihood_factor
		factors.append(likelihood_factor)
		print("Likelihood contribution from %dth element is %.8f" %(index+1,likelihood_factor))
		print(overall_score)
		sys.stdout.flush()
		#print(starting_el)
	np.savez('OverallScores/Hogg_element_likelihoods.npz',
				elements=elements_init,
				likelihood_factors=factors,
				element_mean = element_mean,
				element_sigma = element_sigma)	
				
	np.save("OverallScores/Hogg_score - "+str(a.yield_table_name_sn2)+\
	","+str(a.yield_table_name_agb)+", "+str(a.yield_table_name_1a)+".npy",overall_score)
				
	return overall_score
	
def Hogg_errors():
	"""
	This function computes the overall Hogg score with errors.
	Median and errors (16/84 percentile) are estimated by running the process 10 times.
	"""
	from .overall_scores import overall_Hogg	
	import numpy as np
	from .parameter import ModelParameters
	a = ModelParameters()
	
	scores = []
	for _ in range(10):
		tmp = overall_Hogg()
		scores.append(np.log10(tmp))
			
	median = np.median(scores)
	lower = np.percentile(scores,15.865)
	upper = np.percentile(scores,100-15.865)
	
	print("Average LOO-CV score over 10 iterations is %.2f + %.2f - %.2f" %(median,median-lower,upper-median))
	np.savez("OverallScores/ErrorHogg - "+str(a.yield_table_name_sn2)+", "+str(a.yield_table_name_agb)+", "+str(a.yield_table_name_1a)+".npz",
				median=median,lower=lower,upper=upper)
	return median, median-lower,upper-median