import cv2
import numpy as np
import random
import os
import keras.backend as K

from keras.layers import Conv2D, Input, UpSampling2D, concatenate, MaxPooling2D
from keras import optimizers
from keras.models import Model
from keras.activations import sigmoid
from keras.engine.topology import Layer
from keras.callbacks import LearningRateScheduler

def load_data(data_files,label_files, height, width):
    
    data = []
    label = []
    
    for data_file in data_files:
        hazy_image = cv2.imread(data_path + "/" + data_file)
        if hazy_image.shape != (height, width, 3):
            hazy_image = cv2.resize(hazy_image, (width, height), interpolation = cv2.INTER_AREA)
        label_file = label_files[label_files.index(data_file[0:4] + data_file[-4:])]
        trans_map = cv2.imread(label_path + "/" + label_file)
        if trans_map.shape != (height, width, 3):
            trans_map = cv2.resize(trans_map, (width, height), interpolation = cv2.INTER_AREA)
        data.append(hazy_image)
        label.append(trans_map)
    
    data = np.asarray(data) / 255.0
    label = np.asarray(label) / 255.0
    
    return data, label

def get_batch(data_files, label_files, batch_size, height, width):
   
    while 1:
        for i in range(0, len(data_files), batch_size):
            x, y = load_data(data_files[i : i+batch_size], label_files, height, width)
            
            yield x, y
            
def scheduler(epoch):
    if epoch % 20 == 0 and epoch != 0:
        lr = K.get_value(sgd.lr)
        K.set_value(sgd.lr, lr - 0.1)
        print("lr changed to {}".format(lr - 0.1))
    return K.get_value(sgd.lr)


class Linear_Comb(Layer):
    '''
    https://keunwoochoi.wordpress.com/2016/11/18/for-beginners-writing-a-custom-keras-layer/
    https://blog.csdn.net/u013084616/article/details/79295857
    http://kibo.tech/2018/08/12/56-%E8%AE%A9Keras%E6%9B%B4%E9%85%B7%E4%B8%80%E4%BA%9B%EF%BC%81Keras%E6%A8%A1%E5%9E%8B%E6%9D%82%E8%B0%88/
    '''
    
    def __init__(self, output_dim, **kwargs):
        self.output_dim = output_dim
        super(Linear_Comb, self).__init__(**kwargs)
         
    def build(self, input_shape):
        self.kernel = self.add_weight(name = 'kernel', 
                                      shape = (input_shape[3],self.output_dim), 
                                      initializer='uniform', 
                                      trainable=True)
        self.bias = self.add_weight(name='bias', 
                                    shape=(self.output_dim,),
                                    initializer='uniform', 
                                    trainable=True)
        super(Linear_Comb, self).build(input_shape)
    
    def call(self, x):
        return sigmoid(K.dot(x, self.kernel) + self.bias)
    
def coarse_net():
    input_image = Input(shape = (None, None, 3))
    conv1 = Conv2D(5, (11,11), strides=(1, 1), padding='valid', activation='relu',kernel_initializer='random_normal')(input_image)
    mp1 = MaxPooling2D(pool_size = (2,2), padding = 'valid')(conv1)
    up1 = UpSampling2D(size=(2,2), interpolation = 'nearest')(mp1)
    conv2 = Conv2D(5, (9,9), strides=(1, 1), padding='valid', activation='relu',kernel_initializer='random_normal')(up1)
    mp2 = MaxPooling2D(pool_size = (2,2), padding = 'valid')(conv2)
    up2 = UpSampling2D(size=(2,2), interpolation = 'nearest')(mp2)
    conv3 = Conv2D(10, (7,7), strides=(1, 1), padding='valid', activation='relu',kernel_initializer='random_normal')(up2)
    mp3 = MaxPooling2D(pool_size = (2,2), padding = 'valid')(conv3)
    up3 = UpSampling2D(size=(2,2), interpolation = 'nearest')(mp3)
    linear = Linear_Comb(1)(up3)
    #print(linear.shape)
    model = Model(inputs = input_image, outputs = linear)
    return model

def fine_net(coarse_model):
    input_image = Input(shape = (None, None, 3))
    conv1 = Conv2D(4, (7,7), strides=(1, 1), padding='valid', activation='relu',kernel_initializer='random_normal')(input_image)
    mp1 = MaxPooling2D(pool_size = (2,2), padding = 'valid')(conv1)
    up1 = UpSampling2D(size=(2,2), interpolation = 'nearest')(mp1)
    concat1 = concatenate([up1, coarse_model.predict(input_image)], axis = -1)
    conv2 = Conv2D(5, (5,5), strides=(1, 1), padding='valid', activation='relu',kernel_initializer='random_normal')(concat1)
    mp2 = MaxPooling2D(pool_size = (2,2), padding = 'valid')(conv2)
    up2 = UpSampling2D(size=(2,2), interpolation = 'nearest')(mp2)
    conv3 = Conv2D(10, (3,3), strides=(1, 1), padding='valid', activation='relu',kernel_initializer='random_normal')(up2)
    mp3 = MaxPooling2D(pool_size = (2,2), padding = 'valid')(conv3)
    up3 = UpSampling2D(size=(2,2), interpolation = 'nearest')(mp3)
    linear = Linear_Comb(1)(up3)
    model = Model(inputs = input_image, outputs = linear)
    return model

if __name__ =="__main__":
    
    sgd = optimizers.SGD(lr=0.001, momentum=0.9, decay=5e-4, nesterov=False)
    p_train = 0.7
    width = 320
    height = 240
    batch_size = 100
    
    data_path = '/home/jianan/Incoming/dongqin/OTS/OTS001'
    label_path = '/home/jianan/Incoming/dongqin/OTS/clear_images'                      
    data_files = os.listdir(data_path) # seems os reads files in an arbitrary order
    label_files = os.listdir(label_path)
    
    random.seed(0)  # ensure we have the same shuffled data every time
    random.shuffle(data_files) 
    x_train = data_files[0: round(len(data_files) * p_train)]
    x_val =  data_files[round(len(data_files) * p_train) : len(data_files)]
    steps_per_epoch = len(x_train) // batch_size + 1
    steps = len(x_val) // batch_size + 1
    reduce_lr = LearningRateScheduler(scheduler)
    
    coarse_model = coarse_net()
    coarse_model.compile(optimizer = sgd, loss = 'mean_squared_error')
    coarse_model.fit_generator(generator = get_batch(x_train, label_files, batch_size, height, width), 
                        steps_per_epoch=steps_per_epoch, epochs = 70, validation_data = 
                        get_batch(x_val, label_files, batch_size, height, width), validation_steps = steps,
                        use_multiprocessing=True, 
                        shuffle=False, initial_epoch=0, callbacks = [reduce_lr])
    coarse_model.save('/home/jianan/Incoming/dongqin/DeHaze/AOD-Net/aodnet.model')
    print('coarse model generated')
    
    fine_model = fine_net(coarse_model)
    fine_model.compile(optimizer = sgd, loss = 'mean_squared_error')
    fine_model.fit_generator(generator = get_batch(x_train, label_files, batch_size, height, width), 
                        steps_per_epoch=steps_per_epoch, epochs = 70, validation_data = 
                        get_batch(x_val, label_files, batch_size, height, width), validation_steps = steps,
                        use_multiprocessing=True, 
                        shuffle=False, initial_epoch=0, callbacks = [reduce_lr])
    coarse_model.save('/home/jianan/Incoming/dongqin/DeHaze/AOD-Net/aodnet.model')
    print('fine model generated')






















