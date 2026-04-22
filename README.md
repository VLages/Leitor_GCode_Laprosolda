# Como Rodar o Programa

Olá, Rosa.

Para visualizar o estágio atual do software é necessário baixar todos os arquivos e seus respectivos diretórios, extrair eles para fora do arquivo .zip e rodar o arquivo mainGL.py (Clique duas vezes em cima dele). Caso ocorra algum erro de inicialização, baixe as seguintes bibliotecas no terminal do computador:

 ```pip install PyQt5 numpy PyOpenGL PyOpenGL_accelerate```

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

## Dia 5

Feitos desse dia:

- Agora a simulaçao pode ser rodada de qualquer linha do código, apenas selecione com o mouse a linha desejada e apertar os botões de play ou de retroceder
> Nota: Descobri que o principal erro não era exatamente o programa ler sempre do z = 0 mas sim não conseguir identificar GCodes com um 0 seguido do número definido (por exemplo, não era possível ler linhas como G00, G01 ou G04, agora isso é possível)
- Tentei realizar a implementação de um viewcube assim como outros programas de CAS possuem, porém estava dando muitos erros e deixei para ser implementado outro dia
- O problema de leitura foi concertado, agora GCodes com z diferente de 0 podem ser lidos normalmente (pelo menos não apresentaram nenhum defeito os modelos enviados à mim)
- A matriz que representa a banca de trabalho foi colocada no [0,0,0] da área de trabalho com um valor fixo provisório de 500 x 500 mm (Ainda falta concertar bug - linhas do grid crescem infinitamente dependendo do angulo da camera)

# Dia 6

- Bug das linhas do grid crescerem ao infinito corrigido
- Foi implementado no botão de configurações a função de pode ajustar o tamanho do grid (tanto nos valores fixos das bancadas 1m x 1m, 70cm x 50cm, 113cm x 80cm, quanto para quaisquer valores que o usuário desejar)
- Foi implementado a redenrização de um cilindro que representa a ponta da tocha em escala realista (40 mm de comprimento com ponta cônica)
- Agora toda vez ao abrir um GCode novo, a opção de ver objeto completo vai estar selecionada
- Posição inicial da câmera ajustada
- A movimentação da câmera foi ajustada, deixou de ser uma movimentação primitiva agora parece uma movimentação profissional de um programa de CAD. (Porém após essa implementação o programa pareceu ficar mais travado o renderizar maiores quantidades de linhas. Mas vizualizando a peça por camadas, o programa deixa de ficar travado)

## Dia 7

- Foi implementado um Cube Viewer no lugar do Axis onde só mostrava os eixos X, Y, Z, agora está mais intuitivo de visualizar diferentes perspectivas da peça
- Foi implementado a opção de ser colocado um substrado sob a renderização do GCode, onde ele sempre surgira no [0,0,0] e com uma altura fixa de 5 mm, porém o usuário pode mudar o comprimento dos eixos X e Y manulamente.
- Foram feitas analises de Big O para identificar gargalhos de FPS e de memória do software, as soluções para melhorar a otimização foram iplementadas.
> Nota: É importante ressaltar que o software ainda está travando bastante, posteriormente será feito uma mudança para C++ e OpenGL, já que os gargalhos de processamento estão relacionados com o python e com PyQt5

## Dia 8

- Foi adicionado um sistema de alerta caso o substrato esteja menor que os limites da peça, tal sistema que poderá ser utilizado posteriormente para os fixadores, caso eles invadam o espaço do GCode.
- Avancei bastante com a implementação do OpenGL, conseguir fazer o software renderizar com essa nova biblioteca, mas ainda faltam muitos ajustes para ficar igual o resultado de antes. Como proximos passos, documentarei aqui o que precisa ser feito:
    - Ajustar o Cube Viewer que está com as faces e com a matrix de rotação invertido
    - Arrumar as linhas de extrução e do travel, colocar suas respectiveis transparencias e ordem de prioridade ao aparecem no programa (linhas que ainda serão lidas pelo código estão se sobrepondo as linhas que o código está lendo)
    - Concertar o mal funcionamento do alerta do substrato e melhorar a visualização das bordas do substrato
    - Deixar as linhas do grid mais invisiveis (estão atrapalhando muito na visualização da altura da primeira camada)

## Dia 9

- Foi corrigido o o Cube Viewer, agora ele gira acompanhando os movimentos certos da camera e representa o lado certo da peça (Tudo aplicado em OpenGL)
- As linhas de extrução agora são mais visiveis e mais finas, assim como era na versão antiga em PyQt 5
- O alerta do substrato está funcionando perfeitamente
- As linhas do grid estão finas como um fio de cabelo, não atrapalhando a visualização da peça
> Gostaria de enautecer a marca alcançada de 360 quadros por segundo nessa nova versão em OpenGL, onde antes ficava estaguinado em 15 quadros por segundo
- Foi solucionado o problema de ajustar a velocidade, pois ao colocar o programa na velocidade maxima e voltar aos 50%, o programa ficava mais devagar do que estava antes.
    - Um bug foi dectado, ao ativar o substrato as linhas que mostram as próximas linhas ao serem extrudadas e as que já foram lidas estãom ficam hiper finas quase invisiveis 
    - Implementar a opção de colocar fixadores

## Dia 10

- Foi corrigido o bug das linhas invisiveis
- Ajustes nas cores do programa foram feitas afim de melhorar o maximo conforto do usuário
- Reajustei os arquivos do repositório. Agora para testar o programa basta apenas baixar todos os arquivos e clicar duas vezes no arquivo mainGL.py
- A opção de colocar fixadores foi implementada com sucesso, agora basta apenas corrigir alguns bugs:
    - Corrigir a aba de colocar fixadores para também ser ajustada para o light mode
    - fixadores nas quinas do substrato podem ser colocados um dentro do outro (corrigir colisão das pontas com outros fixadores)
    - O botão para alternar entre o modo Light e Dark fica um pouco bugado ao ser apertado pela primeira vez
    - Com a adição dos fixadores o programa voltou a ficar pesado. Proxima etapa será focar na otimização

## Dia 11

- Novos testes foram feitos e o programa correspondeu muito bem tanto no meu computador de Desktop (mantendo estável em 120 FPS com o GCode mais pesado que eu tinha e todas as configurações ativadas) e no meu notebook que é mais fraco (mantendo estável em 50 FPS com o GCode mais pesado e todas as configurações ativadas). Caso seja necessário farei futuras atualizações para deixar o software mais otimizado.
- Foi corrigido um bug envolvendo o botão de cancelar na aba de colocar fixadores. Agora apertar o botão de cancelar na aba de configurações ira realmente cancelar sua ação
- Foi corrigido o bug do botão de mudar o tema do programa o ser clicado pela primeira vez
- As cores da aba de posicionar os fixadores tiveram cores adaptadas para o tema claro também
