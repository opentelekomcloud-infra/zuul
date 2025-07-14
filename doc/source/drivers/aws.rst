:orphan:

.. attr:: provider[aws]
   :type: dict

   .. attr:: abstract
      :type: bool

   .. attr:: connection
      :type: str

   .. attr:: flavor-defaults
      :type: dict

      .. attr:: imds-http-tokens

         .. value:: optional

         .. value:: required

      .. attr:: iops
         :type: int

      .. attr:: public-ipv4
         :type: bool

      .. attr:: public-ipv6
         :type: bool

      .. attr:: throughput
         :type: int

      .. attr:: userdata
         :type: str

      .. attr:: volume-size
         :type: int

      .. attr:: volume-type
         :type: str

   .. attr:: flavors
      :type: dict

      A list of flavors associated with this provider.

      .. attr:: dedicated-host
         :type: bool

      .. attr:: description
         :type: str

      .. attr:: ebs-optimized
         :type: bool

      .. attr:: fleet
         :type: dict

         .. attr:: allocation-strategy

            .. value:: prioritized

            .. value:: price-capacity-optimized

            .. value:: capacity-optimized

            .. value:: diversified

            .. value:: lowest-price

         .. attr:: instance-types
            :type: str

      .. attr:: imds-http-tokens

         .. value:: optional

         .. value:: required

      .. attr:: instance-type
         :type: str

      .. attr:: iops
         :type: int

      .. attr:: market-type

         .. value:: on-demand

         .. value:: spot

      .. attr:: name
         :type: str

      .. attr:: public-ipv4
         :type: bool

      .. attr:: public-ipv6
         :type: bool

      .. attr:: throughput
         :type: int

      .. attr:: userdata
         :type: str

      .. attr:: volume-size
         :type: int

      .. attr:: volume-type
         :type: str

   .. attr:: image-defaults
      :type: dict

      .. attr:: architecture
         :type: str

      .. attr:: connection-port
         :type: int

      .. attr:: connection-type
         :type: str

      .. attr:: ena-support
         :type: bool

      .. attr:: image-format

         .. value:: ova

         .. value:: vhd

         .. value:: vhdx

         .. value:: vmdk

         .. value:: raw

      .. attr:: imds-http-tokens

         .. value:: optional

         .. value:: required

      .. attr:: imds-support

         .. value:: v2.0

         .. value:: null

      .. attr:: import-method

         .. value:: snapshot

         .. value:: image

         .. value:: ebs-direct

      .. attr:: import-timeout
         :type: int

      .. attr:: iops
         :type: int

      .. attr:: python-path
         :type: str

      .. attr:: shell-type
         :type: str

      .. attr:: throughput
         :type: int

      .. attr:: userdata
         :type: str

      .. attr:: username
         :type: str

      .. attr:: volume-size
         :type: int

      .. attr:: volume-type
         :type: str

   .. attr:: images
      :type: list

      A list of images associated with this provider.

   .. attr:: images[cloud]
      :type: dict

      These are the attributes available for a Cloud image.

      .. attr:: branch
         :type: str

      .. attr:: connection-port
         :type: int

      .. attr:: connection-type
         :type: str

      .. attr:: description
         :type: str

      .. attr:: image-filters
         :type: dict

         .. attr:: name
            :type: str

         .. attr:: values
            :type: str

      .. attr:: image-id
         :type: str

      .. attr:: imds-http-tokens

         .. value:: optional

         .. value:: required

      .. attr:: import-timeout
         :type: int

      .. attr:: iops
         :type: int

      .. attr:: name
         :type: str

      .. attr:: python-path
         :type: str

      .. attr:: shell-type
         :type: str

      .. attr:: throughput
         :type: int

      .. attr:: type

         .. value:: cloud

      .. attr:: userdata
         :type: str

      .. attr:: username
         :type: str

      .. attr:: volume-size
         :type: int

      .. attr:: volume-type
         :type: str

   .. attr:: images[zuul]
      :type: dict

      These are the attributes available for a Zuul image.

      .. attr:: architecture
         :type: str

      .. attr:: branch
         :type: str

      .. attr:: connection-port
         :type: int

      .. attr:: connection-type
         :type: str

      .. attr:: description
         :type: str

      .. attr:: ena-support
         :type: bool

      .. attr:: image-format

         .. value:: ova

         .. value:: vhd

         .. value:: vhdx

         .. value:: vmdk

         .. value:: raw

      .. attr:: imds-http-tokens

         .. value:: optional

         .. value:: required

      .. attr:: imds-support

         .. value:: v2.0

         .. value:: null

      .. attr:: import-method

         .. value:: snapshot

         .. value:: image

         .. value:: ebs-direct

      .. attr:: import-timeout
         :type: int

      .. attr:: iops
         :type: int

      .. attr:: name
         :type: str

      .. attr:: python-path
         :type: str

      .. attr:: shell-type
         :type: str

      .. attr:: tags
         :type: dict

      .. attr:: throughput
         :type: int

      .. attr:: type

         .. value:: zuul

      .. attr:: userdata
         :type: str

      .. attr:: username
         :type: str

      .. attr:: volume-size
         :type: int

      .. attr:: volume-type
         :type: str

   .. attr:: label-defaults
      :type: dict

      .. attr:: az
         :type: str

      .. attr:: boot-timeout
         :type: int

         The time (in seconds) to wait for a node to boot.

      .. attr:: executor-zone
         :type: str

         Specify that a Zuul executor in the specified zone is
         used to run jobs with nodes from this label.

      .. attr:: host-key-checking
         :type: bool

      .. attr:: iam-instance-profile
         :type: dict

         .. attr:: arn
            :type: str

         .. attr:: name
            :type: str

      .. attr:: imds-http-tokens

         .. value:: optional

         .. value:: required

      .. attr:: iops
         :type: int

      .. attr:: key-name
         :type: str

      .. attr:: security-group-id
         :type: str

      .. attr:: subnet-ids
         :type: str

      .. attr:: tags
         :type: dict

      .. attr:: throughput
         :type: int

      .. attr:: userdata
         :type: str

      .. attr:: volume-size
         :type: int

      .. attr:: volume-type
         :type: str

   .. attr:: labels
      :type: dict

      .. attr:: az
         :type: str

      .. attr:: boot-timeout
         :type: int

         The time (in seconds) to wait for a node to boot.

      .. attr:: description
         :type: str

      .. attr:: executor-zone
         :type: str

         Specify that a Zuul executor in the specified zone is
         used to run jobs with nodes from this label.

      .. attr:: flavor
         :type: str

      .. attr:: host-key-checking
         :type: bool

      .. attr:: iam-instance-profile
         :type: dict

         .. attr:: arn
            :type: str

         .. attr:: name
            :type: str

      .. attr:: image
         :type: str

      .. attr:: imds-http-tokens

         .. value:: optional

         .. value:: required

      .. attr:: iops
         :type: int

      .. attr:: key-name
         :type: str

      .. attr:: max-ready-age
         :type: int

      .. attr:: min-ready
         :type: int

      .. attr:: name
         :type: str

      .. attr:: security-group-id
         :type: str

      .. attr:: subnet-ids
         :type: str

      .. attr:: tags
         :type: dict

      .. attr:: throughput
         :type: int

      .. attr:: userdata
         :type: str

      .. attr:: volume-size
         :type: int

      .. attr:: volume-type
         :type: str

   .. attr:: launch-attempts
      :type: int

   .. attr:: launch-timeout
      :type: int

   .. attr:: name
      :type: str

   .. attr:: object-storage
      :type: dict

      .. attr:: bucket-name
         :type: str

   .. attr:: parent
      :type: str

   .. attr:: region
      :type: str

   .. attr:: resource-limits
      :type: dict

      .. attr:: L-01137DCE
         :type: int

      .. attr:: L-0300530D
         :type: int

      .. attr:: L-03F01FD8
         :type: int

      .. attr:: L-09BD8365
         :type: int

      .. attr:: L-1216C47A
         :type: int

      .. attr:: L-13B8FCE8
         :type: int

      .. attr:: L-14F120D1
         :type: int

      .. attr:: L-1586174D
         :type: int

      .. attr:: L-17AF77E8
         :type: int

      .. attr:: L-1945791B
         :type: int

      .. attr:: L-1BBC5241
         :type: int

      .. attr:: L-20F13EBD
         :type: int

      .. attr:: L-24D7D4AD
         :type: int

      .. attr:: L-2753CF59
         :type: int

      .. attr:: L-2C3B7624
         :type: int

      .. attr:: L-30E31217
         :type: int

      .. attr:: L-313524BA
         :type: int

      .. attr:: L-34B43A08
         :type: int

      .. attr:: L-3819A6DF
         :type: int

      .. attr:: L-39926A58
         :type: int

      .. attr:: L-3C82F907
         :type: int

      .. attr:: L-417A185B
         :type: int

      .. attr:: L-43DA4232
         :type: int

      .. attr:: L-4714FFEA
         :type: int

      .. attr:: L-4740F819
         :type: int

      .. attr:: L-4AB14223
         :type: int

      .. attr:: L-4D15192B
         :type: int

      .. attr:: L-5136197D
         :type: int

      .. attr:: L-52EF324A
         :type: int

      .. attr:: L-545AED39
         :type: int

      .. attr:: L-5480EFD2
         :type: int

      .. attr:: L-55E05032
         :type: int

      .. attr:: L-587AA6E3
         :type: int

      .. attr:: L-5C4CD236
         :type: int

      .. attr:: L-5CC9EA82
         :type: int

      .. attr:: L-5D8DADF5
         :type: int

      .. attr:: L-5E3A299D
         :type: int

      .. attr:: L-5E4FB836
         :type: int

      .. attr:: L-5F7FD336
         :type: int

      .. attr:: L-5FA3355A
         :type: int

      .. attr:: L-6222C1B6
         :type: int

      .. attr:: L-67B8B4C7
         :type: int

      .. attr:: L-698B67E5
         :type: int

      .. attr:: L-6B0D517C
         :type: int

      .. attr:: L-6C2C40CC
         :type: int

      .. attr:: L-6E869C2A
         :type: int

      .. attr:: L-7212CCBC
         :type: int

      .. attr:: L-7295265B
         :type: int

      .. attr:: L-74F41837
         :type: int

      .. attr:: L-74FC7D96
         :type: int

      .. attr:: L-75B9BECB
         :type: int

      .. attr:: L-77EE2B11
         :type: int

      .. attr:: L-7A658B76
         :type: int

      .. attr:: L-7F5506AB
         :type: int

      .. attr:: L-80F2B67F
         :type: int

      .. attr:: L-81657574
         :type: int

      .. attr:: L-82ACEF56
         :type: int

      .. attr:: L-84391ECC
         :type: int

      .. attr:: L-84FB37AA
         :type: int

      .. attr:: L-85EED4F7
         :type: int

      .. attr:: L-86A789C3
         :type: int

      .. attr:: L-8814B54F
         :type: int

      .. attr:: L-888B4496
         :type: int

      .. attr:: L-88CF9481
         :type: int

      .. attr:: L-89870E8E
         :type: int

      .. attr:: L-8B27377A
         :type: int

      .. attr:: L-8B7BF662
         :type: int

      .. attr:: L-8CCBD91B
         :type: int

      .. attr:: L-8D142A2E
         :type: int

      .. attr:: L-8D977E7E
         :type: int

      .. attr:: L-8E60B0B1
         :type: int

      .. attr:: L-8FE30D52
         :type: int

      .. attr:: L-9126620E
         :type: int

      .. attr:: L-93155D6F
         :type: int

      .. attr:: L-949445B0
         :type: int

      .. attr:: L-9675FDCD
         :type: int

      .. attr:: L-9721EDD9
         :type: int

      .. attr:: L-97677CE3
         :type: int

      .. attr:: L-98E1FFAC
         :type: int

      .. attr:: L-9CF3C2EB
         :type: int

      .. attr:: L-9D28191F
         :type: int

      .. attr:: L-A0A19F79
         :type: int

      .. attr:: L-A2D59C67
         :type: int

      .. attr:: L-A68CFBF7
         :type: int

      .. attr:: L-A6E7FE5E
         :type: int

      .. attr:: L-A749B537
         :type: int

      .. attr:: L-A8448DC5
         :type: int

      .. attr:: L-A84ABF80
         :type: int

      .. attr:: L-AD667A3D
         :type: int

      .. attr:: L-B10F70D6
         :type: int

      .. attr:: L-B3A130E6
         :type: int

      .. attr:: L-B5D1601B
         :type: int

      .. attr:: L-B601B3B6
         :type: int

      .. attr:: L-B6D6065D
         :type: int

      .. attr:: L-B7208018
         :type: int

      .. attr:: L-B88B9D6B
         :type: int

      .. attr:: L-B89271A9
         :type: int

      .. attr:: L-B90B5B66
         :type: int

      .. attr:: L-BC1589C5
         :type: int

      .. attr:: L-BC9FCC71
         :type: int

      .. attr:: L-BD9BD803
         :type: int

      .. attr:: L-C4EABC2C
         :type: int

      .. attr:: L-C93F66A2
         :type: int

      .. attr:: L-CA51381E
         :type: int

      .. attr:: L-CAE24619
         :type: int

      .. attr:: L-CB4F5825
         :type: int

      .. attr:: L-D037CF10
         :type: int

      .. attr:: L-D0AA08B1
         :type: int

      .. attr:: L-D18FCD1D
         :type: int

      .. attr:: L-D269BEFD
         :type: int

      .. attr:: L-D50A37FA
         :type: int

      .. attr:: L-D6994875
         :type: int

      .. attr:: L-D75D2E84
         :type: int

      .. attr:: L-DA07429F
         :type: int

      .. attr:: L-DB2E81BA
         :type: int

      .. attr:: L-DE3D9563
         :type: int

      .. attr:: L-DE82EABA
         :type: int

      .. attr:: L-DEF8E115
         :type: int

      .. attr:: L-E3A00192
         :type: int

      .. attr:: L-E4BF28E0
         :type: int

      .. attr:: L-E5BCF7B5
         :type: int

      .. attr:: L-E68C3AFF
         :type: int

      .. attr:: L-EA4FD6CF
         :type: int

      .. attr:: L-EA99608B
         :type: int

      .. attr:: L-EC7178B6
         :type: int

      .. attr:: L-EF284EFB
         :type: int

      .. attr:: L-EF30B25E
         :type: int

      .. attr:: L-EF58B059
         :type: int

      .. attr:: L-F035E935
         :type: int

      .. attr:: L-F13A970A
         :type: int

      .. attr:: L-F62CBADB
         :type: int

      .. attr:: L-F7808C92
         :type: int

      .. attr:: L-F8516154
         :type: int

      .. attr:: L-FACBE655
         :type: int

      .. attr:: L-FD252861
         :type: int

      .. attr:: L-FD8E9B9A
         :type: int

      .. attr:: L-FDB0A352
         :type: int

      .. attr:: cores
         :type: int

      .. attr:: instances
         :type: int

      .. attr:: ram
         :type: int

   .. attr:: section
      :type: str


