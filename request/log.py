# -*- coding: utf-8 -*-
#!/usr/bin/env python
#Copyright (c) 2013 Baidu.com, Inc. All Rights Reserved 

import httplib
import threading
import google.protobuf.message

import baidu_realtime_bidding_pb2 


class Record(object):
    def __init__(self, bid_request, status_code, payload):
        #����
        self.bid_request = bid_request
        #������
        self.status = status_code
        #���ص�ԭʼ��Ϣ
        self.payload = payload
        #ͳ��������б�
        self.problems = []
        #���ص�proto ����
        self.bid_response = None

class LoggerException(Exception):
    """ Logger �׳����쳣"""
    pass


class Logger(object):
    """ ��¼���۵������Ϣ"""
    def __iter__(self):
        if not self._done:
            raise LoggerException('Only locked Loggers are iterable.')
        return self

    def __getitem__(self, item):
        if not self._done:
            raise LoggerException('Only locked Loggers are iterable.')
        return self._records[item]

    def next(self):
        if not self._done:
            raise LoggerException('Only locked Loggers can are iterable.')
        if self._current_iteration >= len(self._records):
            self._current_iteration = 0
            raise StopIteration
        c = self._current_iteration
        self._current_iteration += 1
        return self._records[c]

    def __init__(self):
        self._records = []
        self._record_lock = threading.Lock()
        self._current_iteration = 0
        self._done = False

    def Done(self):
        self._record_lock.acquire()
        try:
            self._done = True
        finally:
            self._record_lock.release()
            pass

    def IsDone(self):
        is_done = False
        self._record_lock.acquire()
        try:
            is_done = self._done
        finally:
            self._record_lock.release()
            pass 
        return is_done

    def LogSynchronousRequest(self, bid_request, status_code, payload):
        """ 
        @note:  ��¼���۵�����ͷ���
        @params: 
            bid_request: �������� 
            status_code: ��Ӧ�ķ��ص�״̬��
            payload: ��Ӧ���ص�ԭʼ��Ϣ 
        @return: ��¼�ɹ�����True, ���򷵻�false
        """
        if self.IsDone():
            return False

        self._record_lock.acquire()
        try:
            record = Record(bid_request, status_code, payload)
            self._records.append(record)
        finally:
            self._record_lock.release()
            pass
        return True



class LogSummarizer(object):
    """ ͳ�ƾ��۲�������ļ���"""
    REQUEST_ERROR_MESSAGES = {
          'not-ok': 'The HTTP response code was not 200/OK.',
          }

    RESPONSE_ERROR_MESSAGES = {
          'empty': 'Response is empty (0 bytes).',
          'parse-error': 'Response could not be parsed.',
          'uninitialized': 'Response did not contain all required fields.',
          'response-no-match': 'Response dit not match request.',
          'no-processing-time': 'Response contains no processing time information.',
          'ads-in-ping': 'Response for ping message contains ads.',
          }

    AD_ERROR_TEMPLATE = 'Ad %d: %s'
    AD_ERROR_MESSAGES = {
          'no-param': 'Ad did not contain ', 
          'invalid-sequence-id': 'ad sequence_id is not present in the BidRequest.',
          'max-less-than-min': 'max_cpm <= minimum_cpm',
          }

    def __init__(self, logger):
        """
        @note:  ��ʼ��
        @param:  
            logger: ��¼��logger

        """
        self._logger = logger
        self._requests_sent = 0
        self._responses_ok = 0
        self._responses_successful_without_bids = 0
        self._processing_time_sum = 0
        self._processing_time_count = 0

        # ������ȷ�ķ���
        self._good = []
        # ����ɽ���������������ķ���
        self._problematic = []
        # ���治�ɽ����ķ���
        self._invalid = []
        # ���� �������200�ķ���
        self._error = []


    def Summarize(self):
        """
        @note: ͳ�ƾ���
        """
        for record in self._logger:
            self._requests_sent += 1
            if record.status == httplib.OK:
                self._responses_ok += 1
            else:
                record.problems.append(self.REQUEST_ERROR_MESSAGES['not-ok'])
                self._error.append(record)
                continue
    
            if not record.payload:
                record.problems.append(self.RESPONSE_ERROR_MESSAGES['empty'])
                self._invalid.append(record)
                continue
    
            bid_response = baidu_realtime_bidding_pb2.BidResponse()
            try:
                bid_response.ParseFromString(record.payload)
            except google.protobuf.message.DecodeError:
                record.problems.append(self.RESPONSE_ERROR_MESSAGES['parse-error'])
                self._invalid.append(record)
                continue
    
            if not bid_response.IsInitialized():
                record.problems.append(self.RESPONSE_ERROR_MESSAGES['uninitialized'])
                self._invalid.append(record)
                continue
    
    
            record.bid_response = bid_response
            if bid_response.id != record.bid_request.id:
                record.problems.append(
                      self.RESPONSE_ERROR_MESSAGES['response-no-match'])
                self._problematic.append(record)
                continue
    
    
            if record.bid_request.is_ping:
                self.ValidatePing(record)
            else:
                if not bid_response.ad:
                    self._responses_successful_without_bids += 1
                    self._good.append(record)
                else:
                    for i, ad in enumerate(bid_response.ad):
                        self.ValidateAd(ad, i, record)

            #if not bid_response.HasField('processing_time_ms'):
                #record.problems.append(
                    #self.RESPONSE_ERROR_MESSAGES['no-processing-time'])
            #else:
                #self._processing_time_count += 1
                #self._processing_time_sum += bid_response.processing_time_ms
    
            if record.problems:
                self._problematic.append(record)
            else:
                self._good.append(record)

    def ValidatePing(self, record):
        """
        @note: ��֤ping����
        @param:
            record: Recordʵ��
        """
        bid_response = record.bid_response
        if bid_response.ad:
            record.problems.append(self.RESPONSE_ERROR_MESSAGES['ads-in-ping'])

    def ValidateAd(self, ad, ad_index, record):
        """
        @note: ��֤���
        @params:
            ad: ���صĹ��
            ad_index: ���ع���λ��
            record: Record ʵ��
        """

        ad_type_fields = [
            'sequence_id', 'creative_id', 'max_cpm']

        for field in ad_type_fields:
            if not ad.HasField(field):
                record.problems.append(self.AD_ERROR_TEMPLATE % ( ad_index, self.AD_ERROR_MESSAGES['no-param'] + field ))

        found_adslot = None 
        for adslot in record.bid_request.adslot:
            if adslot.sequence_id == ad.sequence_id:
                found_adslot = adslot

        if not found_adslot:
            record.problems.append(self.AD_ERROR_TEMPLATE % (
                ad_index, self.AD_ERROR_MESSAGES['invalid-sequence-id']))
        else:
            if ad.max_cpm < found_adslot.minimum_cpm:
                record.problems.append(self.AD_ERROR_TEMPLATE % (
                    ad_index, self.AD_ERROR_MESSAGES['max-less-than-min']))
        return 

    def WriteLogFiles(self, good_log, problematic_log, invalid_log, error_log):
        """
        @note: ��� successful/error/problematic/invalid requests ���ļ���
        @param:
            good_log: ��¼��ȷ���۵��ļ������� 
            problematic_log: ��¼�������⾺�۵��ļ������� 
            invalid_log: ��¼�޷������ľ����ļ������� 
            error_log: ��¼����ֵ����200�ľ��۵��ļ������� 
        """

        if self._problematic:
            problematic_log.write('=== Responses that parsed but had problems ===\n')
        for record in self._problematic:
            problematic_log.write('BidRequest:\n')
            problematic_log.write(str(record.bid_request))
            problematic_log.write('\nBidResponse:\n')
            problematic_log.write(str(record.bid_response))
            problematic_log.write('\nProblems:\n')
            for problem in record.problems:
                problematic_log.write('\t%s\n' % problem)

        if self._good:
            good_log.write('=== Successful responses ===\n')
        for record in self._good:
            good_log.write('BidRequest:\n')
            good_log.write(str(record.bid_request))
            good_log.write('\nBidResponse:\n')
            good_log.write(str(record.bid_response))


        if self._invalid:
            invalid_log.write('=== Responses that failed to parse ===\n')
        for record in self._invalid:
            invalid_log.write('BidRequest:\n')
            invalid_log.write(str(record.bid_request))
            invalid_log.write('\nPayload represented as a python list of bytes:\n')
            byte_list = [ord(c) for c in record.payload]
            invalid_log.write(str(byte_list))

        if self._error:
            error_log.write('=== Requests that received a non 200 HTTP response ===\n')
        for record in self._error:
            error_log.write('BidRequest:\n')
            error_log.write(str(record.bid_request))
            error_log.write('HTTP response status code: %d\n' % record.status)
            error_log.write('\nPayload represented as a python list of bytes:\n')
            byte_list = [ord(c) for c in record.payload]
            error_log.write(str(byte_list))


    def PrintReport(self):
        """Prints a summary report."""
        print '=== Summary of Baidu Real-time Bidding test ==='
        print 'Requests sent: %d' % self._requests_sent
        print 'Responses with a 200/OK HTTP response code: %d' % self._responses_ok
        print 'Responses with a non-200 HTTP response code: %d' % len(self._error)
        print 'Good responses (no problems found): %d' % len(self._good)
        print 'Invalid (unparseable) with a 200/OK HTTP response code: %d' % len( self._invalid)
        print 'Parseable responses with problems: %d' % len(self._problematic)
        #if self._processing_time_count:
            #print 'Average processing time in milliseconds %d' % ( self._processing_time_sum * 1.0 / self._processing_time_count)
        if self._responses_successful_without_bids == self._requests_sent:
            print 'ERROR: None of the responses had bids!'
