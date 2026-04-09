# Como Rodar o Programa

Olá, Rosa.

Para visualizar o estágio atual do software, é necessário baixar os dois arquivos: “main.py” e “editor_grafico.py” (é importante que ambos estejam na mesma pasta). Em seguida, abra o arquivo “main.py” em um editor de texto (estou utilizando o VSCode) e execute-o normalmente, clicando no botão localizado no canto superior direito, “Run Python File”.

## Dia 1

Hoje, foquei principalmente em compreender o funcionamento do QT Designer. Como resultado, desenvolvi apenas um rascunho inicial de como desejo que o programa se apresente em sua versão final.

Ao abrir o programa, você verá duas caixas brancas:

- A mais estreita, localizada à esquerda, será destinada à exibição do GCode, sendo possível editá-lo diretamente no programa;

- A caixa maior, à direita, será responsável pela visualização do desenho.

Os botões posicionados no rodapé terão as mesmas funções dos botões do NCViewer, porém adaptados para atender às nossas especificações.

## Dia 2

Neste dia, encontrei um vídeo de um desenvolvedor estrangeiro criando um modelo simples de uma engine 3D em Python (https://www.youtube.com/watch?v=M_Hx0g5vFko), utilizando as bibliotecas Pygame, NumPy e Numba. A partir disso, concentrei meus esforços em compreender o funcionamento dessa engine, com o objetivo de adaptá-la e implementá-la em nosso software. 

Em relação ao desenvolvimento do programa, foram realizadas algumas melhorias estruturais e funcionais. Inicialmente, reorganizei a disposição dos arquivos, visando facilitar a visualização das tarefas pendentes e melhorar a organização do projeto. Além disso, iniciei a implementação de matrizes e projeções matemáticas, que serão fundamentais para a geração e exibição de objetos em 3D.

Por fim, o botão de “Tela Cheia” foi implementado e encontra-se funcionando corretamente.

## Dia 3

Hoje consegui avançar de forma significativa no desenvolvimento do software. Com o auxílio de inteligências artificiais, implementei o ambiente virtual 3D, capaz de interpretar o resultado final do GCode. Além disso, desenvolvi um parser responsável por ler o GCode e convertê-lo em parâmetros geométricos utilizáveis na renderização do ambiente 3D.

A interação do usuário com o ambiente ainda se encontra em estágio inicial. Nos próximos dias, pretendo focar na melhoria da eficiência e na fluidez dos movimentos, tornando a manipulação do objeto renderizado mais responsiva.

Destaca-se também a otimização do código, que permitiu alcançar altas taxas de quadros na renderização, chegando a aproximadamente 100 frames per second (FPS) no meu computador.

## Dia 4

Segue a lista de tópicos que realizei hoje

- Fiz o upload da nova versão "finalizada" pela inteligencia artificial 
- Removi a opção de mudar as cores de fundo do programa junto com o seu sistema de cache
- Removi a inercia que fazia a peça se mover depois de soltar o botão esquerdo do mouse
- Alterei as cores para azul e vermlho, sendo elas permanentes sem possibilidade de serem alteradas (o azul foi escolhido para representar o Laprosolda e o vermelho para gerar o contraste das linhas G1 e G0)
- Adicionei um novo botão "Auto-camadas" que quando ativado ira mudar automaticamente as camadas enquanto o código estiver rodando
- Agora o boltão de voltar realmente le o código de trás pra frente em vez de apenas voltar uma linha do código
- Foi Adicionado um slider entre os botões de multi-uso e o viewer, e um outro slider entre o editor de texto GCode e o viewer, podendo controlar melhor o tamanho da renderização.

Segue a Lista dos tópicos que precisam ser realizados:

- Concertar a leitura do código (nem sempre todo GCode começa com z = 0)
- Colocar matriz ajustavel para rerpesentar a bancada de trabalho (consequentemente ajustar o recentralizar) 
- Mostrar a ponta da tocha na renderização da peça
- Implementar a função de ter um substrato e fixadores costumisaveis (Baixa prioridade os fixadores)
- Implementar cubo de visualização das fazes arestas e quinas apenas por clicks (Igual dos outros softwares de CAD)

## Dia 5

Feitos desse dia:

- Agora a simulaçao pode ser rodada de qualquer linha do código, apenas selecione com o mouse a linha desejada e apertar os botões de play ou de retroceder
- Tentei realizar a implementação de um viewcube assim como outros programas de CAS possuem, porém estava dando muitos erros e deixei para ser implementado outro dia