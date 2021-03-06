#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Unit tests for the test pipeline verifiers"""

import logging
import tempfile
import unittest

from apitools.base.py.exceptions import HttpError
from hamcrest import assert_that as hc_assert_that
from mock import Mock, patch

from apache_beam.io.fileio import ChannelFactory
from apache_beam.runners.runner import PipelineState
from apache_beam.runners.runner import PipelineResult
from apache_beam.tests import pipeline_verifiers as verifiers
from apache_beam.tests.test_utils import patch_retry


class PipelineVerifiersTest(unittest.TestCase):

  def setUp(self):
    self._mock_result = Mock()
    patch_retry(self, verifiers)

  def test_pipeline_state_matcher_success(self):
    """Test PipelineStateMatcher successes when using default expected state
    and job actually finished in DONE
    """
    pipeline_result = PipelineResult(PipelineState.DONE)
    hc_assert_that(pipeline_result, verifiers.PipelineStateMatcher())

  def test_pipeline_state_matcher_given_state(self):
    """Test PipelineStateMatcher successes when matches given state"""
    pipeline_result = PipelineResult(PipelineState.FAILED)
    hc_assert_that(pipeline_result,
                   verifiers.PipelineStateMatcher(PipelineState.FAILED))

  def test_pipeline_state_matcher_fails(self):
    """Test PipelineStateMatcher fails when using default expected state
    and job actually finished in CANCELLED/DRAINED/FAILED/STOPPED/UNKNOWN
    """
    failed_state = [PipelineState.CANCELLED,
                    PipelineState.DRAINED,
                    PipelineState.FAILED,
                    PipelineState.STOPPED,
                    PipelineState.UNKNOWN]

    for state in failed_state:
      pipeline_result = PipelineResult(state)
      with self.assertRaises(AssertionError):
        hc_assert_that(pipeline_result, verifiers.PipelineStateMatcher())

  test_cases = [
      {'content': 'Test FileChecksumMatcher with single file',
       'num_files': 1,
       'expected_checksum': 'ebe16840cc1d0b4fe1cf71743e9d772fa31683b8'},
      {'content': 'Test FileChecksumMatcher with multiple files',
       'num_files': 3,
       'expected_checksum': '58b3d3636de3891ac61afb8ace3b5025c3c37d44'},
      {'content': '',
       'num_files': 1,
       'expected_checksum': 'da39a3ee5e6b4b0d3255bfef95601890afd80709'},
  ]

  def create_temp_file(self, content, directory=None):
    with tempfile.NamedTemporaryFile(delete=False, dir=directory) as f:
      f.write(content)
      return f.name

  def test_file_checksum_matcher_success(self):
    for case in self.test_cases:
      temp_dir = tempfile.mkdtemp()
      for _ in range(case['num_files']):
        self.create_temp_file(case['content'], temp_dir)
      matcher = verifiers.FileChecksumMatcher(temp_dir + '/*',
                                              case['expected_checksum'])
      hc_assert_that(self._mock_result, matcher)

  @patch.object(ChannelFactory, 'glob')
  def test_file_checksum_matcher_read_failed(self, mock_glob):
    mock_glob.side_effect = IOError('No file found.')
    matcher = verifiers.FileChecksumMatcher('dummy/path', Mock())
    with self.assertRaises(IOError):
      hc_assert_that(self._mock_result, matcher)
    self.assertTrue(mock_glob.called)
    self.assertEqual(verifiers.MAX_RETRIES + 1, mock_glob.call_count)

  @patch.object(ChannelFactory, 'glob')
  def test_file_checksum_matcher_service_error(self, mock_glob):
    mock_glob.side_effect = HttpError(
        response={'status': '404'}, url='', content='Not Found',
    )
    matcher = verifiers.FileChecksumMatcher('gs://dummy/path', Mock())
    with self.assertRaises(HttpError):
      hc_assert_that(self._mock_result, matcher)
    self.assertTrue(mock_glob.called)
    self.assertEqual(verifiers.MAX_RETRIES + 1, mock_glob.call_count)


if __name__ == '__main__':
  logging.getLogger().setLevel(logging.INFO)
  unittest.main()
