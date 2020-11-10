from collections import OrderedDict

#Basic Information descriptions
basic_info = {'Basic Information':"Other", 
              'Information de base':'Autre', 
              'Información básica':'Otro',
              'Informações básicas': 'Outra',
              'Informação básica':'Outra'}

#Basic info translations
basicinfo_translations = {"country_code":['Código del país','Cód país','Code du pays', 'Country code'],
                          "monitor_code":['Codigo del monitor','Cód monitor', 'Code du moniteur', 'Monitor code'],
                          "newspaper_name":['Periódico', 'Jornal', 'Journal', 'Newspaper'],
                          "channel":['Canal', 'Estação', 'Channel'],                          
                          "start_time": ['Horario de comienzo del noticiero', 'Horário de início do noticiário', 'Heure début d’émission', 'Newscast start time'],
                          "num_female_anchors":['Número de presentadoras en el noticiero','Nr. de jornalistas âncoras mulheres','"Nr. de jornal. âncoras mulheres',
                                                'Nombre de présentatrices dans l’émission','Number of female anchors'],
                          "num_male_anchors":['Número de presentadores en el noticiero','Nr. de jornalistas âncoras homens',
                                               'Nr. de jornal. âncoras mulheres','Nombre de présentateurs dans l’émission','Number of male anchors'],
                          "website_name":["Nombre del sitio web","Nome do sitio",'Nom du site Web','Website name'],
                          "website_url":['URL'],
                          "time_accessed":['Fecha/hora de acceso','Acesso em (data)','Date/heure d´accès', 'Date/time accessed'],
                          "offline_presence":['Version impresa o "offline"?', 'Presenca offline?','Présence hors ligne?', 'Offline presence?'],
                          "media_name":['Nombre del medio','Nome do veículo', 'Nom du média', 'Media name'],
                          "twitter_handle":['Nombre de usuario de Twitter', 'Usuário do Twitter', "Nom d'utilisateur Twitter", 'Twitter handle']}

#Coding sheetname mapping
sheetname_mapping = {"Print": ['NewspaperCoding', 'CODAGE POUR JOURNAUX', 'CODIFICACIÓN PARA PERIÓDICOS', 'CODIFICAÇÃO DE JORNAIS'],
                     "Radio":['RadioCoding', "CODAGE D'EMMISSION RADIO",'CODIFICACIÓN PARA RADIO','CODIFICAÇÃO DE RADIO'],
                     "Television": ['TelevisionCoding','CODAGE D’ÉMISSION DE TÉLÉVISION','CODIFICACIÓN PARA TELEVISIÓN','CODIFICAÇÃO DE TELEVISÃO'],
                     "Internet": ['InternetCoding', 'CODAGE POUR INTERNET','CODIFICACIÓN PARA INTERNET','CODIFICAÇÃO INTERNET'],
                     "Twitter": ['TwitterCoding', 'CODAGE POUR TWITTER','CODIFICACIÓN PARA TWITTER','CODIFICAÇÃO TWITTER']}                


people_dict = {'Print': {'10': 'sex', '11': 'age', '12': 'occupation', '13': 'function', '14': 'family_role',
                                   '15': 'victim_or_survivor', '16': 'victim_of', '17': 'survivor_of', '18': 'is_quoted', '19': 'is_photograph',
                                   '20': 'special_qn_1', '21': 'special_qn_2','22': 'special_qn_3'},
                'Radio': {'10': 'sex', '11': 'occupation', '12': 'function','13': 'family_role', '14': 'victim_or_survivor',
                                '15': 'victim_of', '16': 'survivor_of', '17': 'special_qn_1', '18': 'special_qn_2','19': 'special_qn_3'},
                'Television': {'11': 'sex','12': 'age', '13': 'occupation', '14': 'function','15': 'family_role', '16': 'victim_or_survivor',
                                     '17': 'victim_of', '18': 'survivor_of', '19': 'special_qn_1','20': 'special_qn_2','21': 'special_qn_3'},
                'Internet': {'12': 'sex', '13': 'age','14': 'occupation', '15': 'function','16': 'family_role',
                                   '17': 'victim_or_survivor','18': 'victim_of','19': 'survivor_of', '20': 'is_quoted','21': 'is_photograph',
                                   '22': 'special_qn_1', '23': 'special_qn_2','24': 'special_qn_3'},
                'Twitter': {'9': 'sex','10': 'age','11': 'occupation','12': 'function', '13': 'is_photograph',
                                  '14': 'special_qn_1','15': 'special_qn_2','16': 'special_qn_3'}}

journalist_dict = {'Print': {'9': 'sex'},
                    'Radio': {'8': 'role', '9': 'sex'},
                    'Television' :{'8': 'role', '9': 'sex', '10': 'age'},
                    'Internet' :{'10': 'sex', '11': 'age'},
                    'Twitter': {'7': 'sex', '8': 'age'}}

sheet_info = {'Print': {'1':'page_number', 'z':'covid19', '2':'topic','3':'scope', '4':'space',
                                    '5':'equality_rights','6':'about_women','7':'inequality_women','8':'stereotypes',
                                    '24':'further_analysis', '30':'comments'},
              'Radio': {'1':'item_number', 'z':'covid19', '2':'topic'	,'3':'scope',
                                    '4':'equality_rights','5':'about_women','6':'inequality_women','7':'stereotypes',
                                    '20':'further_analysis', '30':'comments'},
              'Television': {'1':'item_number', 'z':'covid19', '2':'topic','3':'scope',
                                    '4':'equality_rights','5':'about_women','6':'inequality_women','7':'stereotypes',
                                    '22':'further_analysis', '30':'comments'},
             'Internet': {'1':'webpage_layer_no', 'z':'covid19', '2':'topic'	,'3':'scope', '4':'shared_via_twitter','5':'shared_via_facebook',
                                    '6':'equality_rights','7':'about_women','8':'inequality_women','9':'stereotypes',
                                    '26':'further_analysis', '30':'comments'},
             'Twitter': {'1':'retweet', 'z':'covid19', '2':'topic',
                                    '3':'equality_rights','4':'about_women','5':'inequality_women','6':'stereotypes',
                                    '18':'further_analysis', '30':'comments'}}
