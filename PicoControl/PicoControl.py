import ctypes
import numpy as np
from picosdk import ps4000a as ps
import matplotlib.pyplot as plt
from picosdk.functions import adc2mV, assert_pico_ok
import time

# PARAMETERS
VOLT_TO_NM = 2 # calibration of volts from sigGen to nm at the laser
ENABLED =  1

class PicoScopeControl():
    def __init__(self, pk_to_pk_voltage = 2000000):
        #parameters
        self.pk_to_pk_voltage = pk_to_pk_voltage

        self.connect()
        self.set_channel(channel="CH_A",channel_range = 7, analogue_offset = 0.0)
        self.set_memory(sizeOfOneBuffer = 500,numBuffersToCapture = 10,Channel = "CH_A")

    def __del__(self):
        # Stop the scope
        # handle = chandle
        self.status["stop"] = ps.ps4000aStop(self.chandle)
        assert_pico_ok(self.status["stop"])

        # Disconnect the scope
        # handle = chandle
        self.status["close"] = ps.ps4000aCloseUnit(self.chandle)
        assert_pico_ok(self.status["close"])

        # Display status returns
        print(self.status)

    def plot_trace(self):
        # Create time data
        time = np.linspace(0, (self.totalSamples - 1) * self.actualSampleIntervalNs, self.totalSamples)

        # Plot data from channel A and B
        plt.plot(time, self.adc2mVChAMax[:])
        plt.plot(time, self.adc2mVChBMax[:])
        plt.xlabel('Time (ns)')
        plt.ylabel('Voltage (mV)')
        plt.show()

    def get_trace(self):
        # Begin streaming mode:
        sampleInterval = ctypes.c_int32(250)
        sampleUnits = ps.PS4000A_TIME_UNITS['PS4000A_US']
        # We are not triggering:
        maxPreTriggerSamples = 0
        autoStopOn = 1
        # No downsampling:
        downsampleRatio = 1
        self.status["runStreaming"] = ps.ps4000aRunStreaming(self.chandle,
                                                        ctypes.byref(sampleInterval),
                                                        sampleUnits,
                                                        maxPreTriggerSamples,
                                                        self.totalSamples,
                                                        autoStopOn,
                                                        downsampleRatio,
                                                        ps.PS4000A_RATIO_MODE['PS4000A_RATIO_MODE_NONE'],
                                                        self.sizeOfOneBuffer)
        assert_pico_ok(self.status["runStreaming"])

        actualSampleInterval = sampleInterval.value
        self.actualSampleIntervalNs = actualSampleInterval * 1000

        print("Capturing at sample interval %s ns" % self.actualSampleIntervalNs )

        # Convert the python function into a C function pointer.
        cFuncPtr = ps.StreamingReadyType(self.streaming_callback)

        # Fetch data from the driver in a loop, copying it out of the registered buffers and into our complete one.
        while nextSample < self.totalSamples and not autoStopOuter:
            wasCalledBack = False
            self.status["getStreamingLastestValues"] = ps.ps4000aGetStreamingLatestValues(self.chandle, cFuncPtr, None)
            if not wasCalledBack:
                # If we weren't called back by the driver, this means no data is ready. Sleep for a short while before trying
                # again.
                time.sleep(0.01)

        print("Done grabbing values.")

        # Find maximum ADC count value
        # handle = chandle
        # pointer to value = ctypes.byref(maxADC)
        maxADC = ctypes.c_int16()
        self.status["maximumValue"] = ps.ps4000aMaximumValue(self.chandle, ctypes.byref(maxADC))
        assert_pico_ok(self.status["maximumValue"])

        # Convert ADC counts data to mV
        self.adc2mVChAMax = adc2mV(self.bufferCompleteA, self.channel_range, maxADC)
        self.adc2mVChBMax = adc2mV(self.bufferCompleteB, self.channel_range, maxADC)
        return [self.adc2mVChAMax, self.adc2mVChBMax]
    def set_memory(self,sizeOfOneBuffer = 500,numBuffersToCapture = 10,Channel = "CH_A"):
        self.sizeOfOneBuffer = sizeOfOneBuffer
        self.totalSamples = self.sizeOfOneBuffer * numBuffersToCapture

        # Create buffers ready for assigning pointers for data collection
        self.bufferAMax = np.zeros(shape=sizeOfOneBuffer, dtype=np.int16)
        self.bufferBMax = np.zeros(shape=sizeOfOneBuffer, dtype=np.int16)

        memory_segment = 0
        if Channel == "CH_A":
            self.status["setDataBuffersA"] = ps.ps4000aSetDataBuffers(self.chandle,
                                                             ps.PS4000A_CHANNEL['PS4000A_CHANNEL_A'],
                                                             bufferAMax.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
                                                             None,
                                                             sizeOfOneBuffer,
                                                             memory_segment,
                                                             ps.PS4000A_RATIO_MODE['PS4000A_RATIO_MODE_NONE'])
            assert_pico_ok(self.status["setDataBuffersA"])
        else:
            self.status["setDataBuffersB"] = ps.ps4000aSetDataBuffers(self.chandle,
                                                                      ps.PS4000A_CHANNEL['PS4000A_CHANNEL_B'],
                                                                      bufferAMax.ctypes.data_as(
                                                                          ctypes.POINTER(ctypes.c_int16)),
                                                                      None,
                                                                      sizeOfOneBuffer,
                                                                      memory_segment,
                                                                      ps.PS4000A_RATIO_MODE['PS4000A_RATIO_MODE_NONE'])
            assert_pico_ok(self.status["setDataBuffersB"])

    def set_channel(self, channel="CH_A",channel_range = 7, analogue_offset = 0.0):
        self.channel_range = channel_range
        if channel == "CH_A":
            self.status["setChA"] = ps.ps4000aSetChannel(self.chandle,
                                                    ps.PS4000A_CHANNEL['PS4000A_CHANNEL_A'],
                                                    ENABLED,
                                                    ps.PS4000A_COUPLING['PS4000A_DC'],
                                                    channel_range,
                                                    analogue_offset)
            assert_pico_ok(self.status["setChA"])
        else:
            self.status["setChB"] = ps.ps4000aSetChannel(self.chandle,
                                                         ps.PS4000A_CHANNEL['PS4000A_CHANNEL_B'],
                                                         ENABLED,
                                                         ps.PS4000A_COUPLING['PS4000A_DC'],
                                                         channel_range,
                                                         analogue_offset)
            assert_pico_ok(self.status["setChB"])

    def connect(self):
        '''
        connect to pico
        :return:
        '''
        # Create chandle and status ready for use
        self.chandle = ctypes.c_int16()
        self.status = {}

        # Open PicoScope 2000 Series device
        # Returns handle to chandle for use in future API functions
        self.status["openunit"] = ps.ps4000aOpenUnit(ctypes.byref(self.chandle), None)
        try:
            assert_pico_ok(self.status["openunit"])
        except:
            powerStatus = self.status["openunit"]

            if powerStatus == 286:
                self.status["changePowerSource"] = ps.ps4000aChangePowerSource(self.chandle, powerStatus)
            else:
                raise
            assert_pico_ok(self.status["changePowerSource"])

    def streaming_callback(self,handle, noOfSamples, startIndex, overflow, triggerAt, triggered, autoStop, param):
        # We need a big buffer, not registered with the driver, to keep our complete capture in.
        self.bufferCompleteA = np.zeros(shape=self.totalSamples, dtype=np.int16)
        self.bufferCompleteB = np.zeros(shape=self.totalSamples, dtype=np.int16)
        nextSample = 0
        autoStopOuter = False
        wasCalledBack = False

        global nextSample, autoStopOuter, wasCalledBack
        wasCalledBack = True
        destEnd = nextSample + noOfSamples
        sourceEnd = startIndex + noOfSamples
        self.bufferCompleteA[nextSample:destEnd] = self.bufferAMax[startIndex:sourceEnd]
        self.bufferCompleteB[nextSample:destEnd] = self.bufferBMax[startIndex:sourceEnd]
        nextSample += noOfSamples
        if autoStop:
            autoStopOuter = True



class PicoSigGenControl(PicoScopeControl):
    def __init__(self, pk_to_pk_voltage=2000000):
        super(PicoScopeControl, self).__init__()

    def calculate_scan_width(self):
        self.scan_width = self.pk_to_pk_voltage * VOLT_TO_NM
        return self.scan_width

        # time.sleep(0.01)
        #
        # print("Done grabbing values.")
        #
        # # handle = chandle
        # # pointer to value = ctypes.byref(maxADC)
        # maxADC = ctypes.c_int16()
        # status["maximumValue"] = ps.ps4000aMaximumValue(chandle, ctypes.byref(maxADC))
        # assert_pico_ok(status["maximumValue"])
        #
        # # Convert ADC counts data to mV
        # adc2mVChAMax = adc2mV(bufferCompleteA, channel_range, maxADC)
        # adc2mVChBMax = adc2mV(bufferCompleteB, channel_range, maxADC)
        #
        # # Create time data
        # time = np.linspace(0, (totalSamples - 1) * actualSampleIntervalNs, totalSamples)
        #
        # # Plot data from channel A and B
        # plt.plot(time, adc2mVChAMax[:])
        # plt.plot(time, adc2mVChBMax[:])
        # plt.xlabel('Time (ns)')
        # plt.ylabel('Voltage (mV)')
        # plt.show()
















#         # Stop the scope
#         # handle = chandle
#         status["stop"] = ps.ps4000aStop(chandle)
#         assert_pico_ok(status["stop"])
#
#         # Disconnect the scope
#         # handle = chandle
#         status["close"] = ps.ps4000aCloseUnit(chandle)
#         assert_pico_ok(status["close"])
#
#         # Display status returns
#         print(status)
# enabled = 1
# disabled = 0
# analogue_offset = 0.0
#
# # Set up channel A
# # handle = chandle
# # channel = PS4000A_CHANNEL_A = 0
# # enabled = 1
# # coupling type = PS4000A_DC = 1
# # range = PS4000A_2V = 7
# # analogue offset = 0 V
# channel_range = 7
# status["setChA"] = ps.ps4000aSetChannel(chandle,
#                                         ps.PS4000A_CHANNEL['PS4000A_CHANNEL_A'],
#                                         enabled,
#                                         ps.PS4000A_COUPLING['PS4000A_DC'],
#                                         channel_range,
#                                         analogue_offset)
# assert_pico_ok(status["setChA"])
#
# # Set up channel B
# # handle = chandle
# # channel = PS4000A_CHANNEL_B = 1
# # enabled = 1
# # coupling type = PS4000A_DC = 1
# # range = PS4000A_2V = 7
# # analogue offset = 0 V
# status["setChB"] = ps.ps4000aSetChannel(chandle,
#                                         ps.PS4000A_CHANNEL['PS4000A_CHANNEL_B'],
#                                         enabled,
#                                         ps.PS4000A_COUPLING['PS4000A_DC'],
#                                         channel_range,
#                                         analogue_offset)
# assert_pico_ok(status["setChB"])
#
# # Size of capture
# sizeOfOneBuffer = 500
# numBuffersToCapture = 10
#
# totalSamples = sizeOfOneBuffer * numBuffersToCapture
#
# # Create buffers ready for assigning pointers for data collection
# bufferAMax = np.zeros(shape=sizeOfOneBuffer, dtype=np.int16)
# bufferBMax = np.zeros(shape=sizeOfOneBuffer, dtype=np.int16)
#
# memory_segment = 0
#
# # Set data buffer location for data collection from channel A
# # handle = chandle
# # source = PS4000A_CHANNEL_A = 0
# # pointer to buffer max = ctypes.byref(bufferAMax)
# # pointer to buffer min = ctypes.byref(bufferAMin)
# # buffer length = maxSamples
# # segment index = 0
# # ratio mode = PS4000A_RATIO_MODE_NONE = 0
# status["setDataBuffersA"] = ps.ps4000aSetDataBuffers(chandle,
#                                                      ps.PS4000A_CHANNEL['PS4000A_CHANNEL_A'],
#                                                      bufferAMax.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
#                                                      None,
#                                                      sizeOfOneBuffer,
#                                                      memory_segment,
#                                                      ps.PS4000A_RATIO_MODE['PS4000A_RATIO_MODE_NONE'])
# assert_pico_ok(status["setDataBuffersA"])
#
# # Set data buffer location for data collection from channel B
# # handle = chandle
# # source = PS4000A_CHANNEL_B = 1
# # pointer to buffer max = ctypes.byref(bufferBMax)
# # pointer to buffer min = ctypes.byref(bufferBMin)
# # buffer length = maxSamples
# # segment index = 0
# # ratio mode = PS4000A_RATIO_MODE_NONE = 0
# status["setDataBuffersB"] = ps.ps4000aSetDataBuffers(chandle,
#                                                      ps.PS4000A_CHANNEL['PS4000A_CHANNEL_B'],
#                                                      bufferBMax.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
#                                                      None,
#                                                      sizeOfOneBuffer,
#                                                      memory_segment,
#                                                      ps.PS4000A_RATIO_MODE['PS4000A_RATIO_MODE_NONE'])
# assert_pico_ok(status["setDataBuffersB"])
#
# # Begin streaming mode:
# sampleInterval = ctypes.c_int32(250)
# sampleUnits = ps.PS4000A_TIME_UNITS['PS4000A_US']
# # We are not triggering:
# maxPreTriggerSamples = 0
# autoStopOn = 1
# # No downsampling:
# downsampleRatio = 1
# status["runStreaming"] = ps.ps4000aRunStreaming(chandle,
#                                                 ctypes.byref(sampleInterval),
#                                                 sampleUnits,
#                                                 maxPreTriggerSamples,
#                                                 totalSamples,
#                                                 autoStopOn,
#                                                 downsampleRatio,
#                                                 ps.PS4000A_RATIO_MODE['PS4000A_RATIO_MODE_NONE'],
#                                                 sizeOfOneBuffer)
# assert_pico_ok(status["runStreaming"])
#
# actualSampleInterval = sampleInterval.value
# actualSampleIntervalNs = actualSampleInterval * 1000
#
# print("Capturing at sample interval %s ns" % actualSampleIntervalNs)
#
# # We need a big buffer, not registered with the driver, to keep our complete capture in.
# bufferCompleteA = np.zeros(shape=totalSamples, dtype=np.int16)
# bufferCompleteB = np.zeros(shape=totalSamples, dtype=np.int16)
# nextSample = 0
# autoStopOuter = False
# wasCalledBack = False
#
#
# def streaming_callback(handle, noOfSamples, startIndex, overflow, triggerAt, triggered, autoStop, param):
#     global nextSample, autoStopOuter, wasCalledBack
#     wasCalledBack = True
#     destEnd = nextSample + noOfSamples
#     sourceEnd = startIndex + noOfSamples
#     bufferCompleteA[nextSample:destEnd] = bufferAMax[startIndex:sourceEnd]
#     bufferCompleteB[nextSample:destEnd] = bufferBMax[startIndex:sourceEnd]
#     nextSample += noOfSamples
#     if autoStop:
#         autoStopOuter = True
#
#
# # Convert the python function into a C function pointer.
# cFuncPtr = ps.StreamingReadyType(streaming_callback)
#
# # Fetch data from the driver in a loop, copying it out of the registered buffers and into our complete one.
# while nextSample < totalSamples and not autoStopOuter:
#     wasCalledBack = False
#     status["getStreamingLastestValues"] = ps.ps4000aGetStreamingLatestValues(chandle, cFuncPtr, None)
#     if not wasCalledBack:
# # If we weren't called back by the driver, this means no data is ready. Sleep for a short while before trying
# # again.
# # Find maximum ADC count value