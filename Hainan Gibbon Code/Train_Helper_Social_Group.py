import matplotlib.pyplot as plt
import random
import pickle
import numpy as np
from os import path
import os.path
from sklearn.model_selection import train_test_split
#from sklearn.externals import joblib
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.callbacks import Callback
from tensorflow.keras.callbacks import ModelCheckpoint
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score,precision_score, recall_score, f1_score
from sklearn.metrics import confusion_matrix
from sklearn.utils import shuffle
import itertools
import pandas as pd
import time
from os import listdir
from shutil import copyfile
import pickle

from CNN_Network import *
from Extract_Audio_Helper import *
from Augmentation import augment_data,augment_background, convert_to_image

def execute_audio_extraction(audio_directory, audio_file_name, sample_rate, timestamp_directory,
                            number_seconds_to_extract, save_location):
    
    print ('Reading audio file (this can take some time)...')
    # Read in audio file
    librosa_audio, librosa_sample_rate = librosa.load(audio_directory+audio_file_name, 
                                                  sr=sample_rate)
    
    print ()
    print ('Reading done.')
    
    # Read gibbon labelled timestamp file
    gibbon_timestamps = read_and_process_gibbon_timestamps(timestamp_directory, 
                                   'g_'+audio_file_name[:audio_file_name.find('.wav')]+'.data', 
                                               sample_rate, sep=',')
    # Read non-gibbon labelled timestamp file
    non_gibbon_timestamps = read_and_process_nongibbon_timestamps(timestamp_directory,
                                   'n_'+audio_file_name[:audio_file_name.find('.wav')]+'.data', 
                                               librosa_sample_rate, sep=',')
    # Extract gibbon calls
    gibbon_extracted = extract_all_gibbon_calls(librosa_audio, gibbon_timestamps,
                                            number_seconds_to_extract,1, librosa_sample_rate,0)
    
    # Extract background noise
    noise_extracted = extract_all_nongibbon_calls(librosa_audio, non_gibbon_timestamps,
                                              number_seconds_to_extract,5, librosa_sample_rate,0)
    # Save the extracted data to disk
    pickle.dump(gibbon_extracted, open(save_location+'g_'+audio_file_name[:audio_file_name.find('.wav')]+'.pkl', "wb" ))
    pickle.dump(noise_extracted, open(save_location+'n_'+audio_file_name[:audio_file_name.find('.wav')]+'.pkl', "wb" )) 
    
    del librosa_audio
    print ()
    print ('Extracting segments done. Pickle files saved.')
    
    return gibbon_extracted,noise_extracted
    

def execute_augmentation(gibbon_extracted, 
                                  non_gibbon_extracted, number_seconds_to_extract, sample_rate,
                                  augmentation_amount_noise, augmentation_probability, 
                                  augmentation_amount_gibbon, seed, augment_directory, augment_image_directory,
                                  audio_file_name):
    
    print()
    print ('gibbon_extracted:',gibbon_extracted.shape)
    print ('non_gibbon_extracted:',non_gibbon_extracted.shape)
    
    non_gibbon_extracted_augmented = augment_background(seed, augmentation_amount_noise, 
                                                   augmentation_probability, non_gibbon_extracted, 
                                                   sample_rate, number_seconds_to_extract)
    
    gibbon_extracted_augmented = augment_data(seed, augmentation_amount_gibbon, 
                                             augmentation_probability, gibbon_extracted, 
                                              non_gibbon_extracted_augmented, sample_rate, 
                                              number_seconds_to_extract)
    

    
    sample_amount = gibbon_extracted_augmented.shape[0]
    
    non_gibbon_extracted_augmented = non_gibbon_extracted_augmented[np.random.choice(non_gibbon_extracted_augmented.shape[0], 
                                                                       sample_amount, 
                                                                       replace=True)]
    
    print()
    print('gibbon_extracted_augmented:',gibbon_extracted_augmented.shape)
    print('non_gibbon_extracted_augmented:',non_gibbon_extracted_augmented.shape)
    
    pickle.dump(gibbon_extracted_augmented, 
            open(augment_directory+'g_'+audio_file_name[:audio_file_name.find('.wav')]+'_augmented.pkl', "wb" ))

    pickle.dump(non_gibbon_extracted_augmented, 
                open(augment_directory+'n_'+audio_file_name[:audio_file_name.find('.wav')]+'_augmented.pkl', "wb" ))

    gibbon_extracted_augmented_image = convert_to_image(gibbon_extracted_augmented)
    non_gibbon_extracted_augmented_image = convert_to_image(non_gibbon_extracted_augmented)
    
    print()
    print ('gibbon_extracted_augmented_image:', gibbon_extracted_augmented_image.shape)
    print ('non_gibbon_extracted_augmented_image:', non_gibbon_extracted_augmented_image.shape)
    
    pickle.dump(gibbon_extracted_augmented_image, 
            open(augment_image_directory+'g_'+audio_file_name[:audio_file_name.find('.wav')]+'_augmented_img.pkl', "wb" ))

    pickle.dump(non_gibbon_extracted_augmented_image, 
                open(augment_image_directory+'n_'+audio_file_name[:audio_file_name.find('.wav')]+'_augmented_img.pkl', "wb" ))
    
    del non_gibbon_extracted_augmented, gibbon_extracted_augmented
    
    print()
    print ('Augmenting done. Pickle files saved to...')
    
    return gibbon_extracted_augmented_image, non_gibbon_extracted_augmented_image

def plot_confusion_matrix(cm, classes,
                          normalize=False,
                          title='Confusion matrix',
                          cmap=plt.cm.Blues):
    """
    This function prints and plots the confusion matrix.
    Normalization can be applied by setting `normalize=True`.
    """
    if normalize:
        cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        print("Normalized confusion matrix")
    else:
        print('Confusion matrix, without normalization')

    print(cm)

    plt.imshow(cm, interpolation='nearest', cmap=cmap)
    plt.title(title)
    plt.colorbar()
    tick_marks = np.arange(len(classes))
    plt.xticks(tick_marks, classes, rotation=45)
    plt.yticks(tick_marks, classes)

    fmt = '.2f' if normalize else 'd'
    thresh = cm.max() / 2.
    for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
        plt.text(j, i, format(cm[i, j], fmt),
                 horizontalalignment="center",
                 color="white" if cm[i, j] > thresh else "black")

    plt.ylabel('True label')
    plt.xlabel('Predicted label')
    plt.tight_layout()

def create_seed():
    return random.randint(1, 1000000)


def execute_preprocessing_all_files(training_file, audio_directory, 
                            sample_rate, timestamp_directory,
                            number_seconds_to_extract, save_location,
                            augmentation_amount_noise, augmentation_probability, 
                            augmentation_amount_gibbon, seed, augment_directory, augment_image_directory,
                            number_iterations):
    
    
    with open(training_file) as fp:
        line = fp.readline()

        while line:   
            file_name = line.strip()
            print ('Processing file: {}'.format(file_name))
            
            ## Extract segments from audio files
            gibbon_extracted, non_gibbon_extracted = execute_audio_extraction(audio_directory, 
                                         file_name, sample_rate, timestamp_directory,
                                         number_seconds_to_extract, save_location)
            
            #gibbon_extracted_augmented_image = convert_to_image(gibbon_extracted)
            #non_gibbon_extracted_augmented_image = convert_to_image(non_gibbon_extracted)
            #pickle.dump(gibbon_extracted_augmented_image, 
            #open(augment_directory+'g_'+file_name[:file_name.find('.wav')]+'_augmented_img.pkl', "wb" ))

            #pickle.dump(non_gibbon_extracted_augmented_image, 
            #    open(augment_directory+'n_'+file_name[:file_name.find('.wav')]+'_augmented_img.pkl', "wb" ))
            
            ## Augment the extracted segments
            gibbon_extracted_augmented_image, non_gibbon_extracted_augmented_image = execute_augmentation(gibbon_extracted, 
                                  non_gibbon_extracted, number_seconds_to_extract, sample_rate,
                                  augmentation_amount_noise, augmentation_probability, 
                                  augmentation_amount_gibbon, seed, augment_directory, augment_image_directory,
                                  file_name)
            
            # Read next line
            line = fp.readline()

            
def load_training_images(training_folder, training_file):

    training_data = []
    gibbon_XB = []
    gibbon_XC = []
    gibbon_XD = []
    noise_X = []
    with open(training_file) as fp:
        line = fp.readline()

        while line:

            file_name = line.strip()
            print()
            print('----------------------------------')
            print ('Reading file: {}'.format(file_name))
            file_name = file_name[:file_name.find('.wav')]
        

            if file_name.find('A') != -1 or file_name.find('D') != -1:
                if path.exists(training_folder+'g_'+file_name+'_augmented_img.pkl'):
                    print ('Reading file gibbon augmented file: ', file_name)
                    gibbon_XD.extend(pickle.load(open(training_folder+'g_'+file_name+'_augmented_img.pkl', "rb" )))
            
            if file_name.find('B') != -1 or file_name.find('AB') != -1:
                if path.exists(training_folder+'g_'+file_name+'_augmented_img.pkl'):
                    print ('Reading file gibbon augmented file: ', file_name)
                    gibbon_XB.extend(pickle.load(open(training_folder+'g_'+file_name+'_augmented_img.pkl', "rb" )))
                    
            if file_name.find('C') != -1:
                if path.exists(training_folder+'g_'+file_name+'_augmented_img.pkl'):
                    print ('Reading file gibbon augmented file: ', file_name)
                    gibbon_XC.extend(pickle.load(open(training_folder+'g_'+file_name+'_augmented_img.pkl', "rb" )))

            if path.exists(training_folder+'n_'+file_name+'_augmented_img.pkl'):
                print ('Reading non-gibbon augmented file:', file_name)
                noise_X.extend(pickle.load(open(training_folder+'n_'+file_name+'_augmented_img.pkl', "rb" )))

            # Read next line
            line = fp.readline()


    gibbon_XB = np.asarray(gibbon_XB)
    gibbon_XC = np.asarray(gibbon_XC)
    gibbon_XD = np.asarray(gibbon_XD)
    noise_X = np.asarray(noise_X)

    print()
    print ('B Gibbon features:', gibbon_XB.shape)
    print ('C Gibbon features:', gibbon_XC.shape)
    print ('D Gibbon features:', gibbon_XD.shape)
    print ('Non-gibbon features',noise_X.shape)
    
    return gibbon_XB,gibbon_XC,gibbon_XD, noise_X

def prepare_X_and_Y(gibbon_XB,gibbon_XC, gibbon_XD, noise_X):

    #b --1 ,C -- 2 , D -- 3
    YB_gibbon = np.ones(len(gibbon_XB))
    YC_gibbon = np.ones(len(gibbon_XC))*2
    YD_gibbon = np.ones(len(gibbon_XD))*3
    Y_noise = np.zeros(len(noise_X))
    X = np.concatenate([gibbon_XB,gibbon_XC,gibbon_XD, noise_X])
    #X = np.concatenate([gibbon_XB,gibbon_XD])
    del gibbon_XB,gibbon_XC, gibbon_XD, noise_X
    Y = np.concatenate([YB_gibbon,YC_gibbon,YD_gibbon,Y_noise])
    del YB_gibbon,YC_gibbon,YD_gibbon,Y_noise
    Y = to_categorical(Y)
  
    return X, Y

def train_model(number_iterations, augment_image_directory, training_file,augment_image_directory_validation,validation_file):
    
    print('Loading data...')
    training_files = []
    validation_files = []
    gibbon_XB,gibbon_XC,gibbon_XD,non_gibbon_X = load_training_images(augment_image_directory, training_file)
    gibbon_XB_v,gibbon_XC_v,gibbon_XD_v,non_gibbon_X_v = load_training_images(augment_image_directory_validation, validation_file)
    
    print()
    print ('Data loaded.')
    print ('Processing...')
    X_train, Y_train = prepare_X_and_Y(gibbon_XB,gibbon_XC,gibbon_XD, non_gibbon_X)
    del gibbon_XB,gibbon_XC, gibbon_XD, non_gibbon_X
    X_val, Y_val = prepare_X_and_Y(gibbon_XB_v,gibbon_XC_v,gibbon_XD_v, non_gibbon_X_v)
    del gibbon_XB_v,gibbon_XD_v, gibbon_XD_v, non_gibbon_X_v    
    print ('Processing done.')
    print()
    print ('Shape of X', X_train.shape)
    print ('Shape of Y', Y_train.shape)
    print ('Shape of X', X_val.shape)
    print ('Shape of Y', Y_val.shape)
    
    seed = create_seed()
        
    for experiment_id in range(0,number_iterations):

        print('Iteration {} starting...'.format(experiment_id))

        print ('experiment_id: {}'.format(experiment_id))
        
        #X_train, X_val, Y_train, Y_val = train_test_split(X, Y, test_size=0.20, 
        #                                                    random_state=seed, shuffle = True)
        #X_train, Y_train = shuffle(X_train,Y_train)
        #X_val, Y_val = shuffle(X_val,Y_val)
        
        # Check shape
        print ('X_train:',X_train.shape)
        print ('Y_train:',Y_train.shape)
        print ()
        print ('X_val:',X_val.shape)
        print ('Y_val:',Y_val.shape)

        # Call backs to save weights
        filepath= "Experiments/weights_{}.hdf5".format(seed)
        checkpoint = ModelCheckpoint(filepath, monitor='val_accuracy',verbose=1, save_best_only=True, mode='max')
        #callbacks_list = [checkpoint]
        
        model = network()
        model.compile(loss='categorical_crossentropy', optimizer='adam',metrics=['accuracy'])
        
        model.summary()
        
        start = time.time()

        history = model.fit(X_train, Y_train, validation_data=(X_val, Y_val), 
                  batch_size=8,
                  epochs=50,
                  verbose=2, 
                  callbacks=[checkpoint]) 
                  #class_weight={0:1.,1:1.}
        end = time.time()
        
        model.load_weights("Experiments/weights_{}.hdf5".format(seed))
        
        train_acc = accuracy_score(np.argmax(model.predict(X_train),1),np.argmax(Y_train,1))
        print("training accuracy = ",train_acc)

        val_acc = accuracy_score(np.argmax(model.predict(X_val),1), np.argmax(Y_val,1))
        print("validation accuracy = ",val_acc)

        #test_acc = accuracy_score(np.argmax(model.predict(X_test),1), np.argmax(Y_test,1))
        #print("testing accuracy = ",test_acc)

        # _Compute confusion matrix
        cnf_matrix = confusion_matrix(np.argmax(Y_test,1), np.argmax(model.predict(X_test),1))
        np.set_printoptions(precision=1)
        

        # Plot non-normalized confusion matrix
        plt.figure()
        class_names=['B','D']

        print ()
        print ('Plotting performance on validation data.')
        # Plot normalized confusion matrix
        plt.figure()
        plot_confusion_matrix(cnf_matrix, classes=class_names, normalize=True,
                              title='Normalized confusion matrix')

        plt.show()
        
        TN = cnf_matrix[0][0]
        FP = cnf_matrix[0][1]
        FN = cnf_matrix[1][0]
        TP = cnf_matrix[1][1]

        specificity = TN/(TN+FP)
        sensitivity = TP/(FN+TP)

        FPR = 1 - specificity
        FNR = 1 - sensitivity
        
        performance = []
        performance.append(train_acc)
        performance.append(val_acc)
        performance.append(end-start)
        
        plt.plot(history.history['accuracy'])
        plt.plot(history.history['val_accuracy'])
        plt.title('model accuracy')
        plt.ylabel('accuracy')
        plt.xlabel('epoch')
        plt.legend(['train', 'val'], loc='upper left')
        plt.show()
        
        plt.plot(history.history['loss'])
        plt.plot(history.history['val_loss'])
        plt.title('model loss')
        plt.ylabel('loss')
        plt.xlabel('epoch')
        plt.legend(['train', 'validation'], loc='upper left')
        plt.show()

        np.savetxt('Experiments/train_test_performance_{}.txt'.format(seed), np.asarray(performance), fmt='%f') 
        
        with open('Experiments/history_{}.txt'.format(seed), 'wb') as file_out:
                pickle.dump(history.history, file_out)

        print('Iteration {} ended...'.format(experiment_id))
        print('Results saved to:')
        print('Experiments/train_test_performance_{}.txt'.format(seed))
        print('-------------------')
        time.sleep(1)