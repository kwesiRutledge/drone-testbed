#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.

#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

#  Copyright © 2019 The Regents of the University of Michigan


import math
import csv
import logging
import time
from threading import Timer


import cflib.crtp
from cflib.crazyflie.swarm import CachedCfFactory
from cflib.crazyflie.swarm import Swarm
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.syncLogger import SyncLogger


# Change uris according to your setup
URI0 = 'radio://0/80/2M/E7E7E7E7EA'
URI1 = 'radio://0/80/2M/E7E7E7E7E9'
URI2 = 'radio://0/80/2M/E7E7E7E7EB'
URI3 = 'radio://0/80/2M/E7E7E7E7E7'
URI4 = 'radio://0/80/2M/E7E7E7E7E8'

#drone height parameters, h being the beginning height before consensus
params0 = {'base': 0.15, 'h': 1.0, 'num': 0}
params1 = {'base': 0.15, 'h': 0.4, 'num': 1}
params2 = {'base': 0.15, 'h': 0.6, 'num': 2}
params3 = {'base': 0.15, 'h': 0.3, 'num': 3}
params4 = {'base': 0.15, 'h': 0.8, 'num': 4}


uris = {
	URI0,
	URI1,
	URI2,
	URI3,
	URI4
}

params = {
	URI0: [params0],
	URI1: [params1],
	URI2: [params2],
	URI3: [params3],
	URI4: [params4],
}

currentPos = [0,0,0,0,0]
nextPos = [0,0,0,0,0]
savelog = [[],[],[],[],[]]

def reset_estimator(scf):
	cf = scf.cf

	cf.param.set_value('kalman.resetEstimation', '1')
	time.sleep(0.1)
	cf.param.set_value('kalman.resetEstimation', '0')
	time.sleep(2)



def poshold(cf, t, z):

	steps = t * 10

	for r in range(steps):
		cf.commander.send_hover_setpoint(0, 0, 0, z)
		time.sleep(0.1)

def consensus(currentPosition):
	#print(currentPosition)
	if len(currentPosition) == 2: 
		nextPos[0] = 0.5*(currentPosition[0] + currentPosition[1])
		nextPos[1] = 0.5*(currentPosition[0] + currentPosition[1])
		#print(nextPos)

	elif len(currentPosition) == 3:
		nextPos[0] = 0.5   *(currentPosition[0] + currentPosition[1])
		nextPos[1] = 0.333 *(currentPosition[0] + currentPosition[1] + currentPosition[2])
		nextPos[2] = 0.5   *(currentPosition[1] + currentPosition[2])

	elif len(currentPosition) == 5:
		nextPos[0] = 0.5   *(currentPosition[0] + currentPosition[1])
		nextPos[1] = 0.333 *(currentPosition[0] + currentPosition[1] + currentPosition[2])
		nextPos[2] = 0.333 *(currentPosition[1] + currentPosition[2] + currentPosition[3])
		nextPos[3] = 0.333 *(currentPosition[2] + currentPosition[3] + currentPosition[4])
		nextPos[4] = 0.5   *(currentPosition[3] + currentPosition[4])


def run_sequence(scf, params):
	cf = scf.cf
	base = params['base']
	z = params['h']


	#sets variables for liftoff, beginning, and end heights
	end = 0.3
	base = params['base']
	h = params['h']
	num = params['num']

	# lifts drones off and sends to beginning heights
	poshold(cf, 2, base)
	poshold(cf, 5,h)

	 # The definition of the logconfig can be made before connecting
	log_config = LogConfig(name='Height', period_in_ms=50)
	log_config.add_variable('stateEstimate.z', 'float')
	with SyncLogger(scf, log_config) as logger:
		#sets the runtime
		endTime = time.time() + 45		
		j = 0
		time_elapsed = float(0)


		for log_entry in logger:
			timestamp = log_entry[0]
			data = log_entry[1]
			currentPos[num] = data['stateEstimate.z']
			
			#first runthrough sets begin time of drone, and holds it in
			#current position for another second
			if j == 0:
				begin_T = timestamp
				j = 1
				poshold(cf,1,h)
				print(0)

			#concurrent runthroughs run the consensus algorithm every
			#three seconds and sends the desired position every second
			else:
				time_elapsed = float((timestamp - begin_T))/1000

				#every three seconds runs consensus alg
				if time_elapsed.is_integer() and (int(time_elapsed) % 3) == 0:
					#ensures all three drones have sent their positions before continuuing
					while currentPos[0] == 0 or currentPos[1] == 0 or currentPos[2] == 0 or currentPos[3] == 0 or currentPos[4] == 0:
						time.sleep(0.001)

					#runs consensus algorithm only on one of the 3 parallel programs running
					if num == 0:
						print('running consensus')
						consensus(currentPos)
					#(nextPos)

					#waits till the algorithm runs to continue
					while (nextPos[0] == 0 or nextPos[1] == 0 or nextPos[2] == 0 or nextPos[3] == 0 or nextPos[4] == 0):
						time.sleep(0.001)

					#sends the update positions to the drones
					poshold(cf,1,nextPos[num])
					#print(nextPos)

				#sends position for drones every second
				elif time_elapsed.is_integer():
					if time_elapsed < 3:
						poshold(cf,1,h)
					else:
						poshold(cf,1,nextPos[num])
			#if time_elapsed.is_integer():
				#print(time_elapsed)
				#print(currentPos)

			#appends the time and height data to a log
			savelog[num].append([time_elapsed,currentPos[num]])

			#ends program after endTime seconds
			if time.time() > endTime:
				break


	#poshold(cf,2, end)
	# # Base altitude in meters
	#print(currentPos)

	#sends drones to base height
	poshold(cf, 2, base)

	#saves the data for future use
	str1 = 'testing'
	str2 = '.csv'
	with open(str1+str(num)+str2, 'w') as f:
		writer = csv.writer(f, delimiter=',')
		writer.writerows(savelog[num]) 
	cf.commander.send_stop_setpoint()


if __name__ == '__main__':
	cflib.crtp.init_drivers(enable_debug_driver=False)

	factory = CachedCfFactory(rw_cache='./cache')

	with Swarm(uris, factory=factory) as swarm:
		swarm.parallel(reset_estimator)
	  # swarm.parallel(height_log)
		swarm.parallel(run_sequence, args_dict=params)
