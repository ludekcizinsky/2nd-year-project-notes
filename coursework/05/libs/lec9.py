from termcolor import colored
from collections import defaultdict
import torch
import torch.nn as nn
import torch.optim as optim
import codecs
from .common import MyDataset

LOGCL = 'blue'


class TaggerModel(torch.nn.Module):
    def __init__(self, nwords, ntags, emb_dim, hidden_dim):
        super(TaggerModel, self).__init__()
        self.E = torch.nn.Embedding(nwords, emb_dim)
        self.rnn = nn.RNN(emb_dim, hidden_dim, batch_first=True)
        self.fc = nn.Linear(hidden_dim, ntags)
    
    def forward(self, X):

        yhat, ht = self.rnn(self.E(X))
        out = self.fc(yhat)
        sm = nn.Softmax(dim=2)
        out = sm(out)
        tt = out.size(0)
        out = out.view(tt * X.size(1), -1)

        return out

class RnnPosTagger:

  def __init__(self):
    self.model = None

    self.rawtrain = None
    self.rawdev = None
    self.X_train = None
    self.y_train = None
    self.MX = None
    self.MY = None
    self.X_dev = None
    self.y_dev = None

    self.lr = 0.01
    self.epochs = 10
    self.bsize = 32

  def train_eval(self):
    y_true = self.y_train.view(self.y_train.size(0) * self.X_train.size(1))
    y_hat = self.predict(self.X_train)
    acc = torch.sum(y_true == y_hat)/y_hat.size(0)
    print(f"> Training Accuracy: {acc}")

  def dev_eval(self, filename):

    print(colored('[Evaluation on dev set started]', "magenta" , attrs=['bold']))

    print(colored('[Loading and transforming dev data]', LOGCL, attrs=['bold']))
    self.rawdev = self._load_data(filename)
    mx = max([len(x[0]) for x in self.rawdev])
    self.X_dev, self.y_dev, _, _ = self._raw2idx(self.rawdev, mx, self.MX, self.MY)
    print(f"> Resulting dimension of loaded data: {len(self.rawdev)} x {mx}\n")


    print(colored('[Making predictions]', LOGCL, attrs=['bold']))
    y_true = self.y_dev.view(self.y_dev.size(0) * self.X_dev.size(1))
    y_hat = self.predict(self.X_dev)
    acc = torch.sum(y_true == y_hat)/y_hat.size(0)
    print(f"> Dev Accuracy: {acc}")

  def predict(self, X):

    yhat = self.model.forward(X)
    return torch.argmax(yhat, 1)

  def fit(self, filename):
    
    print(colored('[Training started]', "magenta" , attrs=['bold']))

    print(colored('[Loading and transforming training data]', LOGCL, attrs=['bold']))
    self.rawtrain = self._load_data(filename)
    mx = max([len(x[0]) for x in self.rawtrain])
    self.X_train, self.y_train, self.MX, self.MY = self._raw2idx(self.rawtrain, mx)
    print(f"> Resulting dimension of loaded data: {len(self.rawtrain)} x {mx}\n")

    print(colored('[Preparing model]', LOGCL, attrs=['bold']))
    torch.manual_seed(0)
    self.model = TaggerModel(
        nwords=len(self.MX),
        ntags=len(self.MY),
        emb_dim=100,
        hidden_dim=50 
    )
    print("> Done!\n")

    print(colored('[Learning optimal parameters]', LOGCL, attrs=['bold']))
    traindata = MyDataset(self.X_train, self.y_train)
    optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)
    criterion = torch.nn.CrossEntropyLoss(ignore_index=0, reduction='mean')

    for epoch in range(self.epochs):

      print(f">> Epoch {epoch + 1}")
      trainloader = torch.utils.data.DataLoader(traindata, batch_size=self.bsize, shuffle=True)
      running_loss = 0.0
      
      for i, data in enumerate(trainloader, 0):

        # get the inputs; data is a list of [inputs, labels]
        xx, yy = data

        # zero the parameter gradients
        optimizer.zero_grad()

        # forward + backward + optimize
        out = self.model.forward(xx)

        # Do conversion
        #print(torch.sum(out, 1))
        yy = yy.view(yy.size(0) * mx)
        
        loss = criterion(out, yy)
        loss.backward()
        optimizer.step()

        # print statistics
        running_loss += loss.item()
        bn = 50 # After how many batches do you want to print the loss
        if i % bn  == (bn - 1):    
          print(f'[{epoch + 1}, {i + 1:5d}] loss: {running_loss / bn:.3f}')
          running_loss = 0.0

    self.train_eval()
    print('> Done!\n')

  def _load_data(self, file_name):
    """Code from Rob van der Goot
    read in conll file
    
    :param file_name: path to read from
    :returns: list with sequences of words and labels for each sentence
    """
    data = []
    current_words = []
    current_tags = []

    for line in codecs.open(file_name, encoding='utf-8'):
        line = line.strip()

        if line:
            if line[0] == '#':
                continue # skip comments
            tok = line.split('\t')
            word = tok[0]
            tag = tok[1]

            current_words.append(word)
            current_tags.append(tag)
        else:
            if current_words:  # skip empty lines
                data.append((current_words, current_tags))
            current_words = []
            current_tags = []

    # check for last one
    if current_tags != [] and not raw:
        data.append((current_words, current_tags))

    return data


  def _raw2idx(self, raw, mx, MX=None, MY=None):
    
    if MX is None:
      MX = defaultdict()
      MX.default_factory = MX.__len__

      MY = defaultdict()
      MY.default_factory = MY.__len__

    resx = []
    resy = []
    for x, y in raw:

        t = (mx - len(x))

        tmpx = [] 
        for w in x:
            try:
              tmpx.append(MX[w])
            except KeyError:
              tmpx.append(MX["PAD"])
        tmpx = tmpx + [MX["PAD"]]*t
        resx.append(tmpx)

        tmpy = []
        for l in y:
          try:
            tmpy.append(MY[l])
          except KeyError:
            tmpy.append(MY["PAD"])
        tmpy = tmpy + [MY["PAD"]]*t
        resy.append(tmpy)
    
    MX.default_factory = None
    MY.default_factory = None

    return torch.LongTensor(resx), torch.LongTensor(resy), MX, MY


