import numpy as np
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from cntk import learning_rates_per_sample, DeviceDescriptor, Trainer, sgdlearner, Axis
from cntk.ops import variable, cross_entropy_with_softmax, combine, classification_error, sigmoid, element_times, constant, parameter, times, slice
from cntk.utils import  get_train_loss, cntk_device
from cntk.examples.common.nn import LSTMP_component_with_self_stabilization, embedding, fully_connected_linear_layer, select_last
from cntk.examples.common.mb import create_text_mb_source

def create_mb_source(input_dim, num_output_classes, epoch_size):
    features_config = dict()
    features_config["alias"] = "x"
    features_config["dim"] = input_dim
    features_config["format"] = "sparse"

    labels_config = dict()
    labels_config["alias"] = "y"
    labels_config["dim"] = num_output_classes
    labels_config["format"] = "dense"

    input_config = dict()
    input_config["features"] = features_config
    input_config["labels"] = labels_config

    deserializer_config = dict()
    deserializer_config["type"] = "CNTKTextFormatDeserializer"
    rel_path = r"../../../../../Tests/EndToEndTests/Text/SequenceClassification/Data/Train.ctf"
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)
    deserializer_config["file"] = path    
    deserializer_config["input"] = input_config

    minibatch_config = dict()
    minibatch_config["epochSize"] = epoch_size  
    minibatch_config["deserializers"] = [deserializer_config]

    return create_minibatch_source(minibatch_config)

def LSTM_sequence_classifer_net(input, num_output_classes, embedding_dim, LSTM_dim, cell_dim, device):
    embedding_function = embedding(input, embedding_dim, device)
    LSTM_function = LSTMP_component_with_self_stabilization(embedding_function, LSTM_dim, cell_dim, device)
    thought_vector_function = select_last(LSTM_function)

    return fully_connected_linear_layer(thought_vector_function, num_output_classes, device)

def train_sequence_classifier(device):   
    input_dim = 2000;
    cell_dim = 25;
    hidden_dim = 25;
    embedding_dim = 50;
    num_output_classes = 5;

    features = variable(shape=input_dim, is_sparse=True, name="features")
    classifier_output = LSTM_sequence_classifer_net(features, num_output_classes, embedding_dim, hidden_dim, cell_dim, device)

    label = variable(num_output_classes, dynamic_axes = [Axis.default_batch_axis()], name="labels")
    ce = cross_entropy_with_softmax(classifier_output, label)
    pe = classification_error(classifier_output, label)
    lstm_net = combine([ce.owner, pe.owner, classifier_output.owner], "classifier_model")

    rel_path = r"../../../../../Tests/EndToEndTests/Text/SequenceClassification/Data/Train.ctf"
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)
    cm = create_text_mb_source(path, input_dim, num_output_classes, 0, True, False, "x", "y");

    stream_infos = cm.stream_infos()  
    
    for si in stream_infos:
        if si.m_name == 'features':
            features_si = si
        elif si.m_name == 'labels':
            labels_si = si

    minibatch_size = 200
    lr = lr = learning_rates_per_sample(0.0005)

    minibatch_size_limits = dict()    
    minibatch_size_limits[features_si] = (0,minibatch_size)
    minibatch_size_limits[labels_si] = (0,minibatch_size)

    trainer = Trainer(lstm_net, ce, [sgdlearner(lstm_net.parameters(), lr)])
    
    freq = 1   
    i = 0;
    cntk_dev = cntk_device(device)
    #TODO: replace by while True, and add a stop condition inside the loop
    while True:
        mb=cm.get_next_minibatch(minibatch_size_limits, cntk_dev)
        if  len(mb) == 0:
            break
        arguments = dict()
        arguments[features] = mb[features_si].m_data
        arguments[label] = mb[labels_si].m_data
        
        trainer.train_minibatch(arguments, cntk_dev)

        if i % freq == 0: 
            training_loss = get_train_loss(trainer)
            print("Minibatch " + str(i) + ": CrossEntropy loss = " + str(training_loss)) 

        i += 1


if __name__=='__main__':    
    train_sequence_classifier(-1)
