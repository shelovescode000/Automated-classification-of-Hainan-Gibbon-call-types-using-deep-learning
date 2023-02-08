# Gibbon Social Group Classifier
In this study we describe the development of a classifier usin deep learning for discriminating between Hainan gibbon (Nomascus hainanus) social groups using their calls. 

##Requirements
Install all requirements using pip install 
Numpy
Scipy
Librosa
Pandas
Tensorflow
Sklearn
Pickle
Matplotlib

##Overview
<img src="Hainan Gibbon Code/Summary of Methodology.png">

##Pipeline 
<img src="Hainan Gibbon Code/Pipeline.png">

##Additional Files
CNN_Network.py - view/edit the CNN network
Train_Helper.py - all functions which are used during training
Predict_Helper.py - all functions which are used for prediction
Augmentation.py - all functions which are used to augment the data
Extract_Audio_Helper.py - all functions which are used to extract and preprocess the audio files

##Data 
The training, validation, and testing sets are found in: https://zenodo.org/record/3991714#.YQbtDWgzbIU
