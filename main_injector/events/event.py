import os
import glob
import sys
import getopt
import traceback
import datetime
import yaml
from subprocess import run

import pytz
import numpy as np
import matplotlib.pyplot as plt

from main_injector.utils import send_texts_and_emails
from main_injector.utils import distance
from main_injector.utils import obsSlots
from main_injector.hex import observations
from main_injector.gwhelper import gw_map_configure
from main_injector.trigger import trigger_pages as tp
from main_injector.sky import OneRing

class Event:
    def __init__(self, 
                 skymap_filename: str,
                 master_dir: str,
                 trigger_id: str,
                 mjd: float,
                 config_file: str,
                 official,
                 hasrem):
        """
        Event Base Class.


        Attributes:
        -----------
        skymap_filename: skymap path.
        master_dir:  the directory containing all trigger subdirectories.
        trigger_id: the name of the trigger event that comes from LIGO.
        mjd:        the modified julian date of the event (in FITS header, among other places).
        config_file:     the config filename with the parameters that controls the routine.
        official:
        hasrem:


        Methods:

        modify_filesystem


        --------
        """
        self.config = config_file
        # set up the working directories
        self.modify_filesystem(
            skymap_filename, master_dir, trigger_id, mjd, hasrem)
        work_area = self.work_area

        self.trigger_id = trigger_id
        # read config file
        if config_file["force_recycler_mjd"]:
            self.recycler_mjd = config_file["recycler_mjd"]
        else:
            self.recycler_mjd = self.getmjd(datetime.datetime.now())

        self.event_paramfile = os.path.join(
            work_area, trigger_id + '_params.npz')

        # self.event_paramfile = os.path.join(work_area,
        # '..',
        #  trigger_id + '_params.npz')

        # print(self.event_paramfile)
        # asdf
        # raw_input()
        self.weHaveParamFile = True
        try:
            self.event_params = np.load(self.event_paramfile)
        except:
            self.event_params = {
                'ETA': 'NAN',
                'FAR': 'NAN',
                'ChirpMass': 'NAN',
                'MaxDistance': 'NAN',
                'M1': 'NAN',
                'M2': 'NAN',
                'boc': 'NAN',
                'CentralFreq': 'NAN'
            }

        self.weHaveParamFile = False
        self.official = official

        print("EVENT PARAMFILE:")
        print(self.event_paramfile)
        print(self.event_params.items())
        print(self.weHaveParamFile)

        # asdf
        yaml_dir = os.path.join(work_area, 'strategy.yaml')
        
        run(['cp',
            os.path.join(os.environ["ROOT_DIR"], 'recycler.yaml'),
            yaml_dir
        ])

        print(f'** Copied recycler.yaml to {yaml_dir} for future reference **')

    def modify_filesystem(
        self, skymap_filename: str, master_dir: str,
        trigger_id: str, mjd: float, hasrem: bool
    ) -> None:
        """
        Creates neecessary directories.

        Parameters:
        -----------
        skymap_filename: str
            Directory holding 
        master_dir: str
            Directory holding all the trigger directiores.
        trigger_dir: str
            Directory holding everything to do with a single trigger.
        mjd: float
            Modified Julian date of trigger event.
        hasrem: bool
            True if Event have harassement.

        Returns:
        --------

        """

        skymap_filename = skymap_filename.strip()
        print(skymap_filename)
        trigger_dir = skymap_filename.split('/')[-1].split('.')[0]
        self.trigger_dir = trigger_dir
        self.skymap = skymap_filename

        os.system(f"touch {skymap_filename}.processing")
        if not os.path.exists(f"{master_dir}/{trigger_dir}"):
            os.system(f"mkdir {master_dir}/{trigger_id}")

        self.master_dir = master_dir
        if hasrem:
            work_area = f"{master_dir}/{trigger_dir}/hasrem"
        else:
            work_area = f"{master_dir}/{trigger_dir}/norem"

        os.system(f"cp {skymap_filename.strip()} work_area")
        print('WORK AREA', work_area)

        os.system(f"cp {self.master_dir}/{trigger_id}_params.npz {work_area}")
        print(f"cp {skymap_filename.strip()} {work_area}")
        print("work area "+work_area)

        print("skymaps "+self.skymap)

        # Setup website directories
        website = os.environ["WEB"]
        if not os.path.exists(website):
            os.mkdir(website)

        self.mapspath = os.path.join(work_area, "maps")
        print(work_area)
        if not os.path.exists(self.mapspath):
            print(self.mapspath)
            os.makedirs(self.mapspath)

    
        self.imagespath = f"{website}/Triggers/{trigger_id}\
                            /{work_area.split('/')[-1]}"

        if not os.path.exists(self.imagespath):
            os.makedirs(self.imagespath)
        if not os.path.exists(f"{self.imagespath}/images"):
            os.makedirs(f"{self.imagespath}/images")

        self.website_imagespath = f"{self.imagespath}/{self.trigger_dir}"
        self.website_jsonpath = self.imagespath

        if not os.path.exists(self.website_imagespath):
            os.makedirs(self.website_imagespath)

        self.master_dir = master_dir
        self.work_area = work_area
        self.trigger_id = trigger_id
        self.mjd = mjd
        self.website = website

    def mapMaker(self, trigger_id, skymap, config_file, hasrem, snarf_mi_maps=False, start_slot=-1, do_nslots=-1,  mi_map_dir="./") -> None:
        """

        """
        #skymap_filename, master_dir, trigger_id, mjd, config_file, official, hasrem

        # debug
        debug = config_file["debug"]

        # camera
        camera = config_file["camera"]

       # resolution
        resolution = float(config_file["resolution"])

        overhead = config_file["overhead"]
        #nvisits = config_file["nvisits"]
        allSky = config_file['allSky']

        area_per_hex = config_file["area_per_hex"]
        start_of_season = config_file["start_of_season"]
        end_of_season = config_file["end_of_season"]
        events_observed = config_file["events_observed"]
        skipAll = config_file["skipAll"]
        mjd = self.mjd
        outputDir = self.work_area
        mapDir = self.mapspath
        recycler_mjd = self.recycler_mjd
        kasen_fraction = config_file['kasen_fraction']
        debug = config_file["debug"]
        camera = config_file["camera"]
        resolution = config_file["resolution"]
        do_make_maps = config_file["do_make_maps"]
        do_make_hexes = config_file["do_make_hexes"]
        do_make_jsons = config_file["do_make_jsons"]  # set to false by now
        do_make_gifs = config_file["do_make_gifs"]
        do_strategy = config_file["strategy"]  # False/True
        do_onering = config_file["one_ring"]  # False/True
        days_since_burst = 0
        #days_since_burst = config_file["days_since_burst"]
        '''
    # strategy
        exposure_length_ns= np.array(config_file["exposure_length_NS"],dtype='float')
        filter_list_ns    = config_file["exposure_filter_NS"]
        maxHexesPerSlot_ns= np.array(config_file["maxHexesPerSlot_NS"],dtype='float')
        exposure_length_bh= np.array(config_file["exposure_length_BH"],dtype='float')
        filter_list_bh    = config_file["exposure_filter_BH"]
        maxHexesPerSlot_bh= np.array(config_file["maxHexesPerSlot_BH"],dtype='float')

    # economics analysis for NS and for BH
        hoursAvailable_ns = config_file["time_budget_for_NS"]
        hoursAvailable_bh = config_file["time_budget_for_BH"]
        lostToWeather_ns  = config_file["hours_lost_to_weather_for_NS"]
        lostToWeather_bh  = config_file["hours_lost_to_weather_for_BH"]
        rate_bh           = config_file["rate_of_bh_in_O2"];# events/year
        rate_ns           = config_file["rate_of_ns_in_O2"];# events/year
        hours_used_by_NS  = 0
        hours_used_by_BH  = 0

        '''
        print(self.event_params)
        hoursAvailable = 20.
        self.distance = 1.

        # same day?
        try:
            days_since_burst = config_file["days_since_burst"]
        except:
            pass
    # strategy
        exposure_length_rem = config_file["exposure_length_Rem"]
        filter_list_rem = config_file["exposure_filter_Rem"]
        maxHexesPerSlot_rem = config_file["maxHexesPerSlot_Rem"]
        exposure_length_bh = config_file["exposure_length_BH"]
        filter_list_bh = config_file["exposure_filter_BH"]
        maxHexesPerSlot_bh = config_file["maxHexesPerSlot_BH"]

        # ag added
        exposure_tiling_rem = config_file["exposure_tiling_Rem"]
        exposure_tiling_bh = config_file["exposure_tiling_BH"]
        max_number_of_hexes_to_do = config_file["max_number_of_hexes_to_do"]
        hoursAvailable = 20.
        self.time_budget = hoursAvailable

        print(self.event_params.items())
        #hasremnant = self.event_params['hasremnant']

        if hasrem:
            trigger_type = 'hasrem'
        else:
            trigger_type = 'norem'

    # configure strategy for the event type
        if trigger_type == "hasrem":
            exposure_length = exposure_length_rem
            filter_list = filter_list_rem
            maxHexesPerSlot = maxHexesPerSlot_rem
            tiling_list = exposure_tiling_rem
            propid = config_file['propid_Rem']
        elif trigger_type == "norem":
            exposure_length = exposure_length_bh
            filter_list = filter_list_bh
            maxHexesPerSlot = maxHexesPerSlot_bh
            tiling_list = exposure_tiling_bh
            propid = config_file['propid_BH']

        else:
            raise Exception(
                "trigger_type={}  ! Can only compute BH or Rem".format(trigger_type))
        exposure_length = np.array(exposure_length)

        gif_resolution = config_file['gif_resolution']

        gw_map_control = gw_map_configure.control(resolution, outputDir, debug,
                                                  allSky=allSky, snarf_mi_maps=snarf_mi_maps, mi_map_dir=mi_map_dir,
                                                  gif_resolution=gif_resolution)
        gw_map_trigger = gw_map_configure.Trigger(skymap, trigger_id, trigger_type,
                                                  resolution, days_since_burst=days_since_burst)
        # ag test jul 30
        use_teff = 1.0
        gw_map_strategy = gw_map_configure.Strategy(camera, exposure_length,
                                                    filter_list, tiling_list, maxHexesPerSlot, hoursAvailable, propid, max_number_of_hexes_to_do, kasen_fraction, use_teff)
        # strat need max number of hexes and tiling list

        gw_map_results = gw_map_configure.results()


        if not os.path.exists(outputDir):
            os.makedirs(outputDir)


        #if Strategy:
            # run strategy
        
        """if True:
            OneRing.nike(skymap=, probArea_inner=, probArea_outer=,
                         filter=, expTime_inner=, expTime_outer=,
                         mjd, hexFile=)"""
        #    call onering.py
        if do_make_maps:
            # make the computationally expensive maps of everything
            observations.make_maps(
                gw_map_trigger, gw_map_strategy, gw_map_control, gw_map_results)

        if do_make_hexes:
            # compute the best observations
            observations.make_hexes(
                gw_map_trigger, gw_map_strategy, gw_map_control, gw_map_results,
                start_slot=start_slot, do_nslots=do_nslots)
            # if start_slot = -1, do_nslots = -1, then do whole night, as if called like:
            #    observations.make_hexes(
            #        gw_map_trigger, gw_map_strategy, gw_map_control, gw_map_results)
            # the web page maker version of main injector should default to -1, -1

        if do_make_jsons:
            # make the jsons
            observations.make_jsons(
                gw_map_trigger, gw_map_strategy, gw_map_control, gw_map_results)

        if do_make_gifs:
            observations.makeGifs(
                gw_map_trigger, gw_map_strategy, gw_map_control, gw_map_results)

        allSky = config_file['allSky']

        try:
            eventtype = self.event_params['boc']
        except:
            eventtype = None

        try:
            probhasns = self.event_params['probhasns']
        except:
            probhasns = 0.  # for old maps...
        '''
        if config_file['forceProbHasNS']: probhasns = config_file['probHasNS']

        self.probhasns = probhasns
        gethexobstype = None

        #print 'eventtype',eventtype                                                                                                                                                                                                          
        self.time_budget = hoursAvailable_ns



        if eventtype == 'Burst':
            gethexobstype = 'BH'
            self.distance = 1.
            self.propid = config_file['BBH_propid']
            self.time_budget = hoursAvailable_bh
        elif eventtype == 'CBC':
            #print 'probhasns'*100                                                                                                                                                                                                            
            print('PROB HAS NS',probhasns)
            if probhasns > config_file['probHasNS_threshold']:
                gethexobstype = 'NS'
                try:
                    self.distance = distance.dist_from_map(self.skymap)
                except:
                    print('failed to get distance from map')
                    print('using 1mpc')
                    self.distance = 1.
                self.propid = config_file['BNS_propid']
            else:
                gethexobstype = 'BH'
                self.distance = 1.
                self.propid = config_file['BBH_propid']
                self.time_budget = hoursAvailable_bh

        else: #we dont know what we're looking at... do default obs for lightcurve                                                                                                                                                            
            print('WE DONT KNOW WHAT WERE LOOKING AT!'*5)
            gethexobstype = 'BH'
            self.distance = 1.
            self.propid = config_file['BBH_propid']
            self.time_budget = hoursAvailable_bh

        
        trigger_type = gethexobstype 

    # config_fileure strategy for the event type
        if trigger_type == "NS" :
            hoursAvailable       = hoursAvailable_ns - lostToWeather_ns - hours_used_by_NS
            rate                 = rate_ns
            exposure_length      = exposure_length_ns
            filter_list          = filter_list_ns
            maxHexesPerSlot      = maxHexesPerSlot_ns
        elif trigger_type == "BH" :
            hoursAvailable       = hoursAvailable_bh - lostToWeather_bh - hours_used_by_BH
            rate                 = rate_bh
            exposure_length      = exposure_length_bh
            filter_list          = filter_list_bh 
            maxHexesPerSlot      = maxHexesPerSlot_bh
        else :
            raise Exception(
                "trigger_type={}  ! Can only compute BH or NS".format(trigger_type))
        
        allSky = config_file['allSky']

        exposure_length   = np.array(exposure_length)

        gw_map_control  = gw_map_configure.control( resolution, mapDir, debug, 
                                                    allSky=allSky, snarf_mi_maps=snarf_mi_maps, mi_map_dir = mi_map_dir)
        gw_map_trigger  = gw_map_configure.Trigger( skymap, trigger_id, trigger_type, 
                                                    resolution, days_since_burst=days_since_burst)
        gw_map_strategy = gw_map_configure.Strategy( camera, exposure_length, 
                                                     filter_list, maxHexesPerSlot, hoursAvailable, self.propid)
        gw_map_results = gw_map_configure.results()

        if not os.path.exists(outputDir): os.makedirs(outputDir)
        if not os.path.exists(mapDir): os.makedirs(mapDir)

    
        if do_make_maps :
            # make the computationally expensive maps of everything
            observations.make_maps( 
                gw_map_trigger, gw_map_strategy, gw_map_control, gw_map_results)

        if do_make_hexes :
            # compute the best observations
            #observations.make_hexes( 
            #    gw_map_trigger, gw_map_strategy, gw_map_control, gw_map_results,
            #    start_slot = start_slot, do_nslots= do_nslots)

            observations.make_hexes(
                gw_map_trigger, gw_map_strategy, gw_map_control, gw_map_results)


            # if start_slot = -1, do_nslots = -1, then do whole night, as if called like:
            #    observations.make_hexes( 
            #        gw_map_trigger, gw_map_strategy, gw_map_control, gw_map_results)
            # the web page maker version of main injector should default to -1, -1

        if do_make_jsons :
            # make the jsons 
            observations.make_jsons(gw_map_trigger, gw_map_strategy, gw_map_control)

        if do_make_gifs :
            observations.makeGifs(gw_map_trigger, gw_map_strategy, gw_map_control, gw_map_results, allSky = allSky)

        '''
        ra, dec, id, self.prob, mjd, slotNum, dist = \
            obsSlots.readObservingRecord(self.trigger_id, mapDir)

        self.slotNum = slotNum

        integrated_prob = np.sum(self.prob)
        try:
            print('-'*20+'>', 'LIGO PROB: %.3f \tLIGO X DES PROB: %.3f' %
                  (gw_map_results.sum_ligo_prob, integrated_prob))
        except:
            pass

        self.best_slot = gw_map_results.best_slot
        self.n_slots = gw_map_results.n_slots
        self.first_slot = gw_map_results.first_slot
        self.exposure_length = exposure_length
#        if do_make_maps:
        if 1 == 1:
            np.savez(self.event_paramfile,
                     MJD=self.mjd,
                     ETA=self.event_params['ETA'],
                     FAR=self.event_params['FAR'],
                     ChirpMass=self.event_params['ChirpMass'],
                     MaxDistance=self.event_params['MaxDistance'],
                     DESXLIGO_prob=integrated_prob,
                     LIGO_prob=0.0,  # AG changed gw_map_results.sum_ligo_prob -> 0.0 because sum_ligo_prob doesn't make sense here??? sept 6 2022
                     M1=self.event_params['M1'],
                     M2=self.event_params['M2'],
                     nHexes=self.prob.size,
                     time_processed=self.recycler_mjd,
                     boc=self.event_params['boc'],
                     CentralFreq=self.event_params['CentralFreq'],
                     best_slot=gw_map_results.best_slot,
                     n_slots=gw_map_results.n_slots,
                     first_slot=gw_map_results.first_slot,
                     econ_prob=0,  # self.econ_prob,
                     econ_area=0,  # self.econ_area,
                     need_area=0,  # self.need_area,
                     quality=0,  # self.quality,
                     codeDistance=self.distance,
                     exposure_times=exposure_length,
                     exposure_filter=filter_list,
                     hours=self.time_budget,
                     nvisits=-999,  # config_file['nvisits'],
                     mapname='NAN',
                     filename=self.skymap,
                     gethexobstype=trigger_type,
                     # probhasns=self.probhasns
                     probhasns=probhasns
                     )

        map_dir = mapDir
        jsonname = self.trigger_id + "_" + self.trigger_dir + "_JSON.zip"
        jsonFile = os.path.join(map_dir, jsonname)
        jsonfilelistld = os.listdir(map_dir)
        jsonfilelist = []
        for f in jsonfilelistld:
            if '-tmp' in f:
                os.remove(os.path.join(map_dir, f))
            elif '.json' in f:
                jsonfilelist.append(f)

        os.system('zip -j ' + jsonFile + ' ' + self.mapspath + '/*0.json')
        os.system('cp ' + jsonFile + ' ' + self.website_jsonpath)

        os.system('cp ' + os.path.join(map_dir, self.trigger_id) +
                  '_centered_animate.gif ' + self.website_imagespath)
        os.system('cp ' + os.path.join(map_dir, self.trigger_id) +
                  '_animate.gif ' + self.website_imagespath)
        os.system('cp ' + os.path.join(map_dir, self.trigger_id) +
                  '*.png ' + self.website_imagespath)

        return

    def makeProbabilityPlot(self):
        plt.clf()
        plt.plot(self.slotNum, self.prob, label='Total Prob %.3f' %
                 np.sum(self.prob))
        plt.scatter(self.slotNum, self.prob)
        plt.xlabel('Slot Number')
        plt.ylabel('Probability Per Slot')
        plt.title('decam*ligo')
        plt.legend()
        name = self.trigger_id + "-probabilityPlot.png"
        plt.savefig(os.path.join(self.mapspath, name))
        plt.clf()

    def getContours(self, config_file):
        import matplotlib.pyplot as plt

        # if exposure_length is None:
        #    exposure_length = config_file["exposure_length"]
        exposure_length = self.exposure_length
        image_dir = self.website_imagespath
        map_dir = self.mapspath

        bestslot_name = self.trigger_id + "-" + \
            str(self.best_slot) + "-ligo-eq.png"
        cp_string = os.path.join(
            self.work_area, bestslot_name) + ' ' + image_dir + "/"
        trigger_id = self.trigger_id
        trigger_best_slot = trigger_id + "-" + str(self.best_slot)

        if True:
            bestslot_name = trigger_best_slot + "-maglim-eq.png"
            cp_string = os.path.join(
                map_dir, bestslot_name) + ' ' + image_dir + "/"
            oname = trigger_id + "_limitingMagMap.png"
            os.system('cp ' + cp_string + oname)
            bestslot_name = trigger_best_slot + "-prob-eq.png"
            cp_string = os.path.join(
                map_dir, bestslot_name) + ' ' + image_dir + "/"
            oname = trigger_id + "_sourceProbMap.png"
            os.system('cp ' + cp_string + oname)
            bestslot_name = trigger_best_slot + "-ligo-eq.png"
            cp_string = os.path.join(
                map_dir, bestslot_name) + ' ' + image_dir + "/"
            oname = trigger_id + "_LIGO.png"
            os.system('cp ' + cp_string + oname)
            bestslot_name = trigger_best_slot + "-probXligo-eq.png"
            cp_string = os.path.join(
                map_dir, bestslot_name) + ' ' + image_dir + "/"
            oname = trigger_id + "_sourceProbxLIGO.png"
            os.system('cp ' + cp_string + oname)
            # DESGW observation map
            os.system('cp ' + cp_string + oname)
            # probability plot
            self.makeProbabilityPlot()
            name = trigger_id + "-probabilityPlot.png"
            os.system('cp ' + os.path.join(map_dir, name) + ' ' + image_dir)
            #raw_input('getting contours stopped')

        return

    def makeJSON(self, config_file):

        mapmakerresults = np.load(os.path.join(
            self.work_area, 'mapmaker_results.npz'))

        self.best_slot = mapmakerresults['best_slot']
        self.n_slots = mapmakerresults['n_slots']
        self.first_slot = mapmakerresults['first_slot']
        self.econ_prob = mapmakerresults['econ_prob']
        self.econ_area = mapmakerresults['econ_area']
        self.need_area = mapmakerresults['need_area']
        self.quality = mapmakerresults['quality']

        # DESGW json file (to be files once that is done)
        json_dir = self.website_jsonpath
        map_dir = self.mapspath
        jsonname = self.trigger_id + "_" + self.trigger_dir + "_JSON.zip"
        jsonFile = os.path.join(map_dir, jsonname)
        jsonfilelistld = os.listdir(map_dir)
        jsonfilelist = []
        for f in jsonfilelistld:
            if '-tmp' in f:
                os.remove(os.path.join(map_dir, f))
            elif '.json' in f:
                jsonfilelist.append(f)

        if self.n_slots > 0:
            # get statistics
            ra, dec, id, self.prob, mjd, slotNum, dist = \
                obsSlots.readObservingRecord(self.trigger_id, map_dir)
            self.slotNum = slotNum
            # adding integrated probability to paramfile
            integrated_prob = np.sum(self.prob)
            nHexes = str(self.prob.size)
        else:
            integrated_prob = 0
            nHexes = str(0)

        from time import gmtime, strftime
        timeprocessed = strftime("%H:%M:%S GMT \t %b %d, %Y", gmtime())

        #exptimes = ', '.join(map(str, config_file['exposure_length']))
        #expf = ', '.join(map(str, config_file['exposure_filter']))

        try:
            boc = self.event_params['boc']
        except:
            boc = 'NA'

        # Copy json file to web server for public download
        if not os.path.exists(jsonFile):
            if integrated_prob == 0:
                print("zero probability, thus no jsonFile at ", jsonFile)
            else:
                # try:
                os.chmod(self.mapspath, 0o777)
                for js in os.listdir(self.mapspath):
                    os.chmod(os.path.join(self.mapspath, js), 0o777)

                os.system('zip -j ' + jsonFile + ' ' +
                          self.mapspath + '/*0.json')
                # except:
                #    print "no jsonFiles at ", jsonFile
        else:
            os.remove(jsonFile)
            os.system('zip -j ' + jsonFile + ' ' + self.mapspath + '/*0.json')
            os.system('cp ' + jsonFile + ' ' + self.website_jsonpath)
        return jsonfilelist

    def send_nonurgent_Email(self, sendtexts=False):
        text = 'DESGW Webpage Created for REAL event. See \nhttp://des-ops.fnal.gov:8080/desgw/Triggers/' + self.trigger_id + '/' + \
            self.trigger_id + '_' + self.trigger_dir + \
            '_trigger.html\n\nDO NOT REPLY TO THIS THREAD, NOT ALL USERS WILL SEE YOUR RESPONSE.'
        subject = 'DESGW Webpage Created for REAL event ' + \
            self.trigger_id + ' Map: '+self.trigger_dir+' NOREPLY'
        send_texts_and_emails.send(subject, text, official=self.official)
        print('Email sent...')
        return

    def send_processing_error(self, error, where, line, trace):
        import smtplib
        from email.mime.text import MIMEText

        message = 'Processing Failed for REAL Trigger ' + str(self.trigger_id) + '\n\nFunction: ' + str(
            where) + '\n\nLine ' + str(line) + ' of recycler.py\n\nError: ' + str(error) + '\n\n'
        message += '-' * 60
        message += '\n'
        message += trace
        message += '\n'
        message += '-' * 60
        message += '\n'

        subject = 'REAL Trigger ' + self.trigger_id + \
            ' '+self.trigger_dir + ' Processing FAILED!'
        send_texts_and_emails.send(subject, message, official=self.official)
        print('Email sent...')
        return

    def updateTriggerIndex(self, real_or_sim=None):
        website = self.website
        if real_or_sim == 'real':
            fff = os.path.join(website, 'real-trigger_list.txt')
        if real_or_sim == 'sim':
            fff = os.path.join(website, 'test-trigger_list.txt')

        if not os.path.exists(fff):
            lines = []
        else:
            l = open(fff, 'r')
            lines = l.readlines()
            l.close()

        a = open(fff, 'a')
        if lines == []:
            a.write(self.trigger_id + ' ' + self.work_area + '\n')
        else:
            triggers = []
            for line in lines:
                triggers.append(line.split(' ')[0])
            if not self.trigger_id in np.unique(triggers):
                a.write(self.trigger_id + ' ' + self.work_area + '\n')
        a.close()
        tp.make_index_page(website, real_or_sim=real_or_sim)
        return

    '''def make_cumulative_probs(self):
        GW_website_dir = os.path.join(self.website, '/Triggers/')
        sim_study_dir = '/data/des41.a/data/desgw/maininjector/sims_study/data'
        radecfile = os.path.join(self.work_area, 'maps', self.trigger_id + '-ra-dec-id-prob-mjd-slot.txt')
        cumprobs_file = os.path.join(self.work_area, self.trigger_id + '-and-sim-cumprobs.png') 
        print(['python', './python/cumulative_plots.py', '-d',
               sim_study_dir, '-p', self.work_area, '-e', self.trigger_id,
               '-f', radecfile])
        subprocess.call(['python', './python/cumulative_plots.py', '-d',
               sim_study_dir, '-p', self.work_area, '-e', self.trigger_id, 
                '-f',radecfile])
        os.system('scp '+ cumprobs_file + ' ' + GW_website_dir + self.trigger_id + '/images/')
        '''

    def updateWebpage(self, real_or_sim):
        trigger_id = self.trigger_id
        trigger_dir = self.trigger_dir
        GW_website_dir = self.website
        desweb = "codemanager@desweb.fnal.gov:/des_web/www/html/desgw/"
        GW_website_dir_t = GW_website_dir + "Triggers/"
        desweb_t = desweb + "Triggers/"
        desweb_t2 = desweb + "Triggers/" + trigger_id
        trigger_html = os.path.join(self.master_dir, trigger_id + '_' +
                                    trigger_dir + '_trigger.html')

        print('scp -r ' + GW_website_dir_t + self.trigger_id + ' ' + desweb_t)
        print('scp ' + GW_website_dir + '/* ' + desweb)
        # asdf
        os.system('cp '+trigger_html+' '+GW_website_dir)

        #os.system('scp -r ' + GW_website_dir_t + self.trigger_id + ' ' + desweb_t)
        #os.system('scp ' + GW_website_dir + '/* ' + desweb)
        # master_dir,outfilename,trigger_id,event_paramfile,mapfolder,processing_param_file=None,real_or_sim='real',secondtimearound=False
        print(self.master_dir)
        print(os.path.join(self.master_dir, trigger_id +
              '_' + trigger_dir + '_trigger.html'))
        #os.system('cp '+trigger_html+' '+GW_website_dir)
        print(trigger_id, self.event_paramfile, trigger_dir)

        tp.makeNewPage(self.master_dir, os.path.join(self.master_dir, trigger_id + '_' + trigger_dir +
                       '_trigger.html'), trigger_id, self.event_paramfile, trigger_dir, real_or_sim=real_or_sim)
        print('here1')
        print('scp -r ' + trigger_html + ' ' + desweb_t2 + "/")
        #os.system('scp -r ' + trigger_html + ' ' + desweb_t2 + "/")
        print('here2')
        #os.system('scp -r ' + trigger_html + ' ' + desweb_t2 + '_trigger.html')
        print('here3')
        os.system('cp ' + self.master_dir + '/' + trigger_dir + '/' +
                  trigger_dir + '_recycler.log ' + self.website_jsonpath)
        return

    def getmjd(self, datet):
        mjd_epoch = datetime.datetime(1858, 11, 17)
        print('FIX ME UTC OR NOT?!?')
        mjdd = datet-mjd_epoch
        mjd = 5./24. + mjdd.total_seconds() / 3600. / 24.
        return mjd

    def mjd_to_datetime(self, mjd) -> None:
        mjd_epoch = datetime.datetime(1858, 11, 17, tzinfo=pytz.utc)
        d = mjd_epoch + datetime.timedelta(mjd)
        return d

    def makeObservingPlots(self):
        try:
            if not self.config['skipPlots']:
                # n_plots = observations.makeObservingPlots(
                #    self.n_slots, self.trigger_id, self.best_slot, self.outputDir, self.mapDir, self.camera, allSky=True )

                image_dir = self.website_imagespath
                map_dir = self.mapspath

                bestslot_name = self.trigger_id + "-" + \
                    str(self.best_slot) + "-ligo-eq.png"
                if self.n_slots < 1:
                    # counter = observations.nothingToObserveShowSomething(
                    #    self.trigger_id, self.work_area, self.mapspath)
                    oname = self.trigger_id + "-observingPlot.gif"
                    os.system('cp ' + os.path.join(self.work_area,
                              bestslot_name) + ' ' + os.path.join(image_dir, oname))
                    oname = self.trigger_id + "-probabilityPlot.png"
                    os.system('cp ' + os.path.join(self.work_area,
                              bestslot_name) + ' ' + os.path.join(image_dir, oname))
                # if self.n_slots > 0:
                if True:
                    print('Converting Observing Plots to .gif')
                    files = np.array(glob.glob(os.path.join(
                        map_dir, self.trigger_id)+'-observingPlot-*.png'))
                    split = [i.split('-', 2)[2] for i in files]
                    number = [i.split('.', 1)[0] for i in split]
                    f = np.array(number).astype(np.int)
                    print(f, type(f))
                    maximum = str(np.max(f))
                    minimum = str(np.min(f))
                    os.system('convert $(for ((a='+minimum+'; a<='+maximum+'; a++)); do printf -- "-delay 50 ' + os.path.join(map_dir,
                                                                                                                              self.trigger_id) + '-observingPlot-%s.png " $a; done;) ' + os.path.join(
                        map_dir, self.trigger_id) + '-observingPlot.gif')
                    # os.system('convert -delay 70 -loop 0 '+os.path.join(map_dir,self.trigger_id)+'-observingPlot-*.png '+
                    #          os.path.join(map_dir, self.trigger_id) + '-observingPlot.gif')
                    os.system('cp ' + os.path.join(map_dir,
                              self.trigger_id) + '-observingPlot.gif ' + image_dir)
            #string = "$(ls -v {}-observingPlot*)"

        except:
            e = sys.exc_info()
            exc_type, exc_obj, exc_tb = e[0], e[1], e[2]
            where = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line = exc_tb.tb_lineno
            trace = traceback.format_exc(e)
            print(trace)
            self.send_processing_error(e, where, line, trace)
            sys.exit()