import math
import pandas as pd
import glob, os
import librosa.display
import librosa
import numpy as np
from scipy import signal
from tensorflow.keras.utils import to_categorical
import gc
import matplotlib.pyplot as plt

from CNNNetwork import *

import ntpath

class PredictionHelper:
    
    def __init__(self, species_folder, lowpass_cutoff, 
                 downsample_rate, nyquist_rate, segment_duration, 
                 n_fft, hop_length, n_mels, f_min, f_max, 
                 weights_name):

        self.species_folder = species_folder
        self.lowpass_cutoff = lowpass_cutoff
        self.downsample_rate = downsample_rate
        self.nyquist_rate = nyquist_rate
        self.segment_duration = segment_duration
        self.audio_path = self.species_folder + '/'
        self.testing_files = self.species_folder + '/TestingFiles.txt'
        self.annotations_path = self.species_folder + '/Annotations/'
        self.n_ftt = n_fft
        self.hop_length = hop_length
        self.n_mels = n_mels
        self.f_min = f_min
        self.f_max = f_max
        self.weights_name = weights_name      

    def read_audio_file(self, file_name):
        '''
        file_name: string, name of file including extension, e.g. "audio1.wav"
        
        '''
        # Get the path to the file
        audio_folder = os.path.join(file_name)
        
        # Read the amplitudes and sample rate
        audio_amps, audio_sample_rate = librosa.load(audio_folder, sr=None)
        
        return audio_amps, audio_sample_rate
    
    def create_X_new(self, mono_data, time_to_extract, sampleRate,start_index, 
        end_index, file_name_no_extension, verbose):
        '''
        Create X input data to apply a model to an audio file.
        '''

        X_frequences = []

        sampleRate = sampleRate
        duration = end_index - start_index -time_to_extract+1
        if verbose:
            # Print spme info
            print ('-----------------------')
            print ('start (seconds)', start_index)
            print ('end (seconds)', end_index)
            print ('duration (seconds)', (duration))
            print()
        counter = 0

        end_index = start_index + time_to_extract
        # Iterate over each chunk to extract the frequencies
        for i in range (0, duration):

            if verbose:
                print ('Index:', counter)
                print ('Chunk start time (sec):', start_index)
                print ('Chunk end time (sec):',end_index)

            # Extract the frequencies from the mono file
            extracted = mono_data[int(start_index *sampleRate) : int(end_index * sampleRate)]

            X_frequences.append(extracted)

            start_index = start_index + 1
            end_index = end_index + 1
            counter = counter + 1

        X_frequences = np.array(X_frequences)
        print (X_frequences.shape)
        if verbose:
            print ()

        return X_frequences

    def butter_lowpass(self, cutoff, nyq_freq, order=4):
        normal_cutoff = float(cutoff) / nyq_freq
        b, a = signal.butter(order, normal_cutoff, btype='lowpass')
        return b, a

    def butter_lowpass_filter(self, data, cutoff_freq, nyq_freq, order=4):
        # Source: https://github.com/guillaume-chevalier/filtering-stft-and-laplace-transform
        b, a = self.butter_lowpass(cutoff_freq, nyq_freq, order=order)
        y = signal.filtfilt(b, a, data)
        return y
    
    def downsample_file(self, amplitudes, original_sr, new_sample_rate):
        '''
        Downsample an audio file to a given new sample rate.
        amplitudes:
        original_sr:
        new_sample_rate:
        
        '''
        return librosa.resample(amplitudes, 
                                original_sr, 
                                new_sample_rate, 
                                res_type='kaiser_fast'), new_sample_rate

    def convert_single_to_image(self, audio):
        '''
        Convert amplitude values into a mel-spectrogram.
        '''
        S = librosa.feature.melspectrogram(audio, n_fft=self.n_ftt,hop_length=self.hop_length, 
                                           n_mels=self.n_mels, fmin=self.f_min, fmax=self.f_max)
        
        image = librosa.core.power_to_db(S)
        image_np = np.asmatrix(image)
        image_np_scaled_temp = (image_np - np.min(image_np))
        image_np_scaled = image_np_scaled_temp / np.max(image_np_scaled_temp)
        mean = image.flatten().mean()
        std = image.flatten().std()
        eps=1e-8
        spec_norm = (image - mean) / (std + eps)
        spec_min, spec_max = spec_norm.min(), spec_norm.max()
        spec_scaled = (spec_norm - spec_min) / (spec_max - spec_min)
        S1 = spec_scaled
        
    
        # 3 different input
        return S1

    def convert_all_to_image(self, segments):
        '''
        Convert a number of segments into their corresponding spectrograms.
        '''
        spectrograms = []
        for segment in segments:
            spectrograms.append(self.convert_single_to_image(segment))
        
        
        return np.array(spectrograms)
    
    def add_keras_dim(self, spectrograms):
        spectrograms = np.reshape(spectrograms, 
                                  (spectrograms.shape[0],
                                   spectrograms.shape[1],
                                   spectrograms.shape[2],1))
        return spectrograms
    
    def load_model(self):

        print('Initialising cnn network.')
        networks = CNNNetwork()
        model = networks.custom_CNN_network()

        print('Loading weights: ', self.weights_name)
        model.load_weights("{}".format(self.weights_name))
                
        return model
    
    def predict_all_test_files(self, verbose):
        '''
        Create X and Y values which are inputs to a ML algorithm.
        Annotated files (.svl) are read and the corresponding audio file (.wav)
        is read. A low pass filter is applied, followed by downsampling. A 
        number of segments are extracted and augmented to create the final dataset.
        Annotated files (.svl) are created using SonicVisualiser and it is assumed
        that the "boxes area" layer was used to annotate the audio files.
        '''
        
        if verbose == True:
            print ('Annotations path:',self.annotations_path+"*.svl")
            print ('Audio path',self.audio_path+"*.wav")
        
        # Read all names of the training files
        testing_files = pd.read_csv(self.testing_files, header=None)
        
        # Load the correct model
        model = self.load_model()
        
        df_data_file_name = []
        Test_files = []

        # Iterate over each annotation file
        for testing_file in testing_files.values:
            
            # Initialise dictionary to contain a list of all the seconds
            # which contain calls
            call_seconds = set()
            
            # Keep track of how many calls were found in the annotation files
            total_calls = 0
            
            file = self.annotations_path+'/'+testing_file[0]+'.svl'
            
            # Get the file name without paths and extensions
            file_name_no_extension = file[file.rfind('/')+1:file.find('.')]
            
            print ('                                   ')
            print ('###################################')
            print ('Processing:',file_name_no_extension)
            
            df_data_file_name.append(file_name_no_extension)
            
            # Check if the .wav file exists before processing
            if "Raw_Data/Test"+"\\"+file_name_no_extension+".wav" in glob.glob(self.audio_path+"*.wav"):

                # Read audio file
                audio_amps, original_sample_rate = self.read_audio_file(self.audio_path+file_name_no_extension+'.wav')
                    
                print ('Applying filter')
                # Low pass filter
                filtered = self.butter_lowpass_filter(audio_amps, self.lowpass_cutoff, self.nyquist_rate)

                print ('Downsample')
                # Downsample
                filtered, filtered_sample_rate = self.downsample_file(filtered, 
                                                                      original_sample_rate, self.downsample_rate)

                print ('Creating segments')
                # Split the file into segments for prediction
                segments = self.create_X_new(filtered, self.segment_duration, 
                                        filtered_sample_rate,0, int(len(filtered)/filtered_sample_rate), file_name_no_extension, False)
                print ('Converting to spectrogram')
                spectrograms = self.convert_all_to_image(segments)
                plt.imshow((spectrograms[12]))
                print ('Predicting')
                spectrograms = self.add_keras_dim(spectrograms)
                model_prediction = model.predict(spectrograms)
                # Nonny to make modifications around here
                # Find all predictions which had a softmax value 
                # greater than some threshold
                values = model_prediction
                df = pd.DataFrame(values)
                df.to_csv(file_name_no_extension+'.csv')
                #print(values[0:100])
                values_NG = values[:,0] >= 0.5
                values_B = values[:,1]  >= 0.5
                values_C = values[:,2]  >= 0.5
                values_D = values[:,3]  >= 0.5
                values = values.astype(np.int)
                
                test_file = [file_name_no_extension,len(values_B),sum(values_NG),sum(values_B),sum(values_C),sum(values_D)]
                Test_files.append(test_file)

                #print(values)

                # Clean up
                del spectrograms, filtered, audio_amps
                gc.collect()
                gc.collect()
        pd.DataFrame(Test_files).to_csv('Test Files.csv')
        return