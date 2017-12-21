def get_marked_indices(inputList):
    '''
    RETURN the indices of elements in <inputList> whose value is True
    '''
    ret = []
    for i in range(len(inputList)):
        if inputList[i]: ret.append(i)
    return ret
