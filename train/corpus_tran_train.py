# -*- coding: UTF-8 -*-
import re
import time

# from numpy import sort
# from pyhanlp import HanLP

import config
from bin.term_tuple import NameTerm, WordTerm, CharTerm, WORD_TYPE
from train.get_corpus import get_sql_cpname

from util.tool import read_dic


class Pretreatment:
    def __init__(self):
        # 加载词典
        self.region_dic = read_dic(config.PLACE_FILE, 'region')
        self.industry_dic = read_dic(config.INDUSTRY_FILE, 'industry')
        self.organization_dic = read_dic(config.ORGANIZATION_FILE, 'organization')
        self.all_dic = dict(self.industry_dic + self.organization_dic)
        self.all_dic = sorted(self.all_dic.items(), key=lambda x: len(x[0]), reverse=True)

    def get_train_pretreatment(self, type, inputfile):
        """
        @summary:根据公司名单得到规整训练集，用于训练
         @params：type 控制数据源来源，主要是文本跟数据库参数 mysql/None ,inputfile 文件路径，使用数据库链接时可以为None
         @return:配置文件中已经设置了输出路径 ，这里无返回
        """

        # 获取语料
        if type == 'mysql' and config.MYSQL_ENABLE:
            unprocessed_corpus = get_sql_cpname(['limit:100', 'tabNum:2', 'random:Y'])
        else:
            unprocessed_corpus = read_dic(inputfile)
        # 加工语料
        cp_term_list = []
        i = 0
        for companyname in unprocessed_corpus:
            i += 1
            if isinstance(companyname, tuple):
                cp_name = companyname[0].strip()
                cp_term = self.one_parse(cp_name)
                cp_term_list.append(cp_term)
            elif isinstance(companyname, str):
                if len(companyname) > 40:
                    continue
                cp_name = companyname
                cp_term = self.one_parse(cp_name)
                cp_term_list.append(cp_term)
        # 写出返回
        t = ''.join([str(int(time.time())), '_'])
        companyname_outPath = ''.join([config.CORPUS_PROCRSS_RESULT_PATH, t, 'companyname'])
        crfpp_outPath = ''.join([config.CORPUS_PROCRSS_RESULT_PATH, t, 'set_crf++_model'])
        json_outPath = ''.join([config.CORPUS_PROCRSS_RESULT_PATH, t, 'corpus_Visual.json'])
        cpout = open(companyname_outPath, 'w+')
        outPut = open(crfpp_outPath, 'w+')
        jsonout = open(json_outPath, 'w+')
        for cp in cp_term_list:
            cpout.write(''.join([cp.company_name, '\n']))
            sb = '#SENT_BEG#\tbegin\n'
            sb = ''.join([sb, cp.name_crf_model()])
            sb = ''.join([sb, '#SENT_END#\tend\n\n'])
            outPut.write(str(sb))
            jsonout.write(''.join([cp.name_to_json(), '\n']))
        jsonout.close()
        outPut.close()
        cpout.close()
        return

    def one_parse(self, cp):
        print(cp)
        cp = re.sub('[\(（）\)]', '', cp)
        cp_term = NameTerm(cp)
        # 获取单词与词性
        # segments=HanLP.segment(cp)
        self.match_word_type(cp_term, 'region', self.region_dic)
        self.match_word_type(cp_term, 'another', self.all_dic)
        #
        # self.match_word_type(cp_term, 'industry', self.industry_dic)
        # self.match_word_type(cp_term, 'organization', self.organization_dic)

        # self.match_seg_word_type(cp_term, segments, 'region', self.region_dic)
        # self.match_seg_word_type(cp_term, segments, 'organization', self.organization_dic)
        # self.match_seg_word_type(cp_term, segments, 'industry', self.industry_dic)
        self.get_unknown_type(cp_term)
        cp_term.sort_word_term()
        cp_term.deduplication_word()
        self.modify_illegal_classify(cp_term)
        cp_term.merge_wterm_include_type('U')

        print(cp_term.set_api_json())
        return cp_term

    def modify_illegal_classify(self, cp_term):
        submark = 0
        for word_term in cp_term.words_term:
            # 对分类出中间出现单独的O类型做修正
            if word_term.type == 'O' and len(word_term.word) == 1:
                if submark > 0 and submark < len(cp_term.words_term) - 1:
                    if cp_term.words_term[submark-1].type == 'U' or cp_term.words_term[submark+1].type == 'U':
                        word_term.set_type('U')
                        for char_term in word_term.chars_term:
                            char_term.mark = char_term.mark[:0] + 'U' + char_term.mark[1:]
            submark += 1


        beark_flag = True
        while beark_flag:#对定义一些出现不合理情况进行选择性纠正
            beark_flag=  self.define_event_processing(cp_term)
            cp_term.sort_word_term()
            cp_term.deduplication_word()


    def define_event_processing(self,cp_term):

        qingk2 = ['IU']
        qingk3 = ['IUI']
        qingk4 = []

        deal_flag = False
        contstr = ''

        for word_term in cp_term.words_term:
            type_str = word_term.type
            contstr = ''.join([contstr, type_str])


        for temp in qingk4:
            if temp in contstr:
                test = contstr.index(temp)

        for temp in qingk3:
            if temp in contstr:
                relative_subscript = contstr.index(temp)
                if temp == 'IUI':  # IUI -> I
                    type_u = cp_term.words_term[relative_subscript + 1]
                    type_i2 = cp_term.words_term[relative_subscript + 2]
                    if type_u.s_offset == type_u.e_offset:  # IU(s)I -> I
                        self.merge_two_word_term(type_u, type_i2, 1)
                        return True


        for temp in qingk2:
            if temp in contstr:
                relative_subscript = contstr.index(temp)
                if temp == 'IU':
                    type_i = cp_term.words_term[relative_subscript]
                    type_u = cp_term.words_term[relative_subscript + 1]
                    if type_i.s_offset == type_i.e_offset:  # I(s)U -> U
                        self.merge_two_word_term(type_i, type_u, 1)
                        return True
                    elif type_u.s_offset == type_u.e_offset:  # IU(s) -> I
                        self.merge_two_word_term(type_i, type_u, 0)
                        return True

        return deal_flag

    def merge_two_word_term(self,fr_word_term,be_word_term,keep_who):
        if keep_who == 0:
            fr_word_term.e_offset += len(be_word_term.word)
            fr_word_term.word = ''.join([fr_word_term.word, be_word_term.word])
            set_type = fr_word_term.type
            be_chars_term = be_word_term.chars_term
            for char_term in be_chars_term:
                char_term.mark = ''.join([set_type,'_M'])
            be_chars_term[len(be_chars_term)-1].mark = ''.join([set_type,'_E'])

            last_fr_char_term = fr_word_term.chars_term[len(fr_word_term.chars_term) - 1]
            last_fr_char_term.mark = ''.join([set_type,'_M'])

            for char_term in be_chars_term:
                fr_word_term.add_char_term(char_term)
            return fr_word_term
        else:
            be_word_term.s_offset -= len(fr_word_term.word)
            be_word_term.word = ''.join([fr_word_term.word, be_word_term.word])
            set_type = be_word_term.type
            fr_chars_term = fr_word_term.chars_term
            for char_term in fr_chars_term:
                char_term.mark = ''.join([set_type,'_M'])
            fr_chars_term[0].mark = ''.join([set_type, '_B'])

            first_be_char_term = fr_word_term.chars_term[0]
            first_be_char_term.mark = ''.join([set_type, '_M'])

            for char_term in be_word_term.chars_term:
                fr_word_term.add_char_term(char_term)
            be_word_term.chars_term = fr_word_term.chars_term
            return be_word_term


    def get_unknown_type(self, cp_term):
        cp_name = cp_term.company_name
        for word_term in cp_term.words_term:
            replace_word = ''
            for i in word_term.word:
                replace_word = ''.join([replace_word, '$'])
            cp_name = cp_name[:word_term.s_offset] + replace_word + cp_name[word_term.e_offset + 1:]
        split_list = cp_name.split('$')
        index = 0
        for unknown in split_list:
            unword = unknown.strip()
            if unword:
                index = cp_name.find(unword, index)
                self.struct_word_terms(cp_term, unword, index, 'unkown')

    def match_seg_word_type(self, cp_term, seg_ments, type_name, type_dic):
        c_index = 0
        for segment in seg_ments:
            if segment.word in type_dic:
                self.struct_word_terms(cp_term, segment.word, c_index, type_name)
            c_index += len(segment.word)

    def match_word_type(self, cp_term, type_name, type_dic):
        cp_name = cp_term.company_name
        for type in type_dic:
            c_index = 0
            if isinstance(type, tuple):
                type_word = type[0]
                type_name = type[1]
            elif isinstance(type_dic, dict):
                type_word = type
                type_name = type_dic[type]
            else:
                type_word = type
            if type_word in cp_name:
                while True:
                    c_index = cp_name.find(type_word, c_index)
                    if c_index > - 1 and c_index <= len(cp_name) - 1:
                        if cp_term.iswordUse(c_index, type_word):
                            self.struct_word_terms(cp_term, type_word, c_index, type_name)
                            c_index += len(type_word)
                        else:
                            self.merge_i(cp_term, type_word, c_index, type_name)
                            break
                    else:
                        break

    def merge_i(self, cp_term, type_word, c_index, type_name):
        if type_name != 'industry':
            return
        for i, word_term in enumerate(cp_term.words_term):
            if word_term.type != 'I':
                continue
            if (word_term.s_offset > c_index and word_term.s_offset <= (c_index + len(type_word)) - 1) or \
                (word_term.e_offset >= c_index and word_term.e_offset < (c_index + len(type_word)) - 1):
                merge_str = self.merge_i_str(cp_term.company_name, word_term.word, word_term.s_offset, type_word, c_index)
                index = min(word_term.s_offset, c_index)
                cp_term.remove_word_term(i)
                self.struct_word_terms(cp_term, merge_str, index, type_name)
                c_index -= len(word_term.word)
                c_index += len(merge_str)
                return

    def merge_i_str(self, company_name, word, s_offset, type_word, c_index):
        start_index = min(s_offset, c_index)
        end_index = max(s_offset + len(word) - 1, c_index + len(type_word) - 1)
        return company_name[start_index: end_index + 1]

    def struct_word_terms(self, cp_term, word, index, type_name):
        cp_name = cp_term.company_name
        word_term = WordTerm(word, index, index + len(word) - 1)
        word_term.set_type(WORD_TYPE[type_name])
        se_index = index
        for s_char in word:
            se_index = cp_name.find(s_char, se_index)
            char_term = CharTerm(s_char, se_index, type_name)
            char_term.char_position(index, index + len(word) - 1, se_index)
            word_term.add_char_term(char_term)
        cp_term.add_word_term(word_term)


if __name__ == '__main__':
    pt = Pretreatment()

    #pt.get_train_pretreatment('mysql','/mnt/vol_0/wnd/usr/cmb_in/语料预处理结果/180504/1525001802_companyname')
    pt.one_parse('大庆市鸿缘福经贸有限公司')

