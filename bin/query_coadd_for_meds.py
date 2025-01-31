#! /usr/bin/env python3
# $Id: query_coadd_for_meds.py 48316 2019-03-01 20:00:27Z rgruendl $
# $Rev:: 48316                            $:  # Revision of last commit.
# $LastChangedBy:: rgruendl               $:  # Author of last commit.
# $LastCha
"""
Query code to obtain images inputs, head files, and zeropoints to make inputs for MEDs.
"""

verbose = 0

######################################################################################

if __name__ == "__main__":

    import argparse
    import os
    import despydb.desdbi
    import time
    import yaml
    import intgutils.queryutils as queryutils
    import mepipelineappintg.meds_query as mq
    import mepipelineappintg.coadd_query as cq
    import mepipelineappintg.mepochmisc as mepochmisc
    import mepipelineappintg.metadetect_pizza_cutter_tools as mdetpizza

    svnid = "$Id: query_coadd_for_meds.py 48316 2019-03-01 20:00:27Z rgruendl $"

    parser = argparse.ArgumentParser(description='Query code to obtain image inputs for COADD/multiepoch pipelines.')
    parser.add_argument('-A', '--pfw_attempt_id', action='store', type=str, default=None, required=False,
                        help='Processing attempt used to discover inputs.')
    parser.add_argument('-o', '--outfile', action='store', type=str, required=True,
                        help='Output list to be returned for the framework')
    parser.add_argument('--zeropoint', action='store', type=str, default='ZEROPOINT',
                        help='ZEROPOINT table to use in queries. (Default=ZEROPOINT, "NONE" results in all ZP fixed at magbase)')
    parser.add_argument('--zsource', action='store', type=str, default=None,
                        help='SOURCE constraint on ZEROPOINT table to use in queries. (Default=None)')
    parser.add_argument('--zversion', action='store', type=str, default=None,
                        help='VERSION constraint on ZEROPOINT table to use in queries. (Default=None)')
    parser.add_argument('--zflag', action='store', type=str, default=None,
                        help='FLAG constraint on ZEROPOINT table to use in queries. (Default=None)')
    parser.add_argument('--bandlist', action='store', type=str, default='g,r,i,z,Y',
                        help='Comma separated list of bands to be COADDed (Default="g,r,i,z,Y").')
    parser.add_argument('--zpt2', action='store', type=str, default=None,
                        help='ZEROPOINT table to use secondary ZPT queries. (Default=None)')
    parser.add_argument('--z2source', action='store', type=str, default=None,
                        help='SOURCE constraint on secondary ZPT queries. (Default=None)')
    parser.add_argument('--z2version', action='store', type=str, default=None,
                        help='VERSION constraint on secondary ZPT queries. (Default=None)')
    parser.add_argument('--z2flag', action='store', type=str, default=None,
                        help='FLAG constraint on secondary ZPT queries. (Default=None)')
    parser.add_argument('--archive', action='store', type=str, default='desar2home',
                        help='Archive site where data are being drawn from')
    parser.add_argument('--magbase', action='store', type=float, default=30.0,
                        help='Fiducial/reference magnitude for COADD (default=30.0)')
    parser.add_argument('--segmap', action='store_true', default=False,
                        help='Flag to also collect associated segmap images')
    parser.add_argument('--bkgimg', action='store_true', default=False,
                        help='Flag to also collect associated bkgd images')
    parser.add_argument('--psfmodel', action='store_true', default=False,
                        help='Flag to also collect associated psfmodel files')
    parser.add_argument('--usepiff', action='store_true', default=False,
                        help='Flag to use PIFF psfmodel (rather than PSFex')
    parser.add_argument('--pifftag', action='store', type=str, default=None,
                        help='Proctag TAG containing PIFF afterburner products (PIFF models)')
    parser.add_argument('--imglist', action='store', type=str, default=None,
                        help='Optional output of a txt-file listing showing expnum, ccdnum, band, zeropoint')
    parser.add_argument('--ima_list', action='store', default=None,
                        help='Filename with list of returned IMG list')
    parser.add_argument('--head_list', action='store', default=None,
                        help='Filename with list of returned HEADFILE list')
    parser.add_argument('--bkg_list', action='store', default=None,
                        help='Filename with list of returned BKG list')
    parser.add_argument('--seg_list', action='store', default=None,
                        help='Filename with list of returned SEGMAP list')
    parser.add_argument('--psf_list', action='store', default=None,
                        help='Filename with list of returned PSFMODEL list')
    parser.add_argument('-s', '--section', action='store', type=str, default=None,
                        help='section of .desservices file with connection info')
    parser.add_argument('-S', '--Schema', action='store', type=str, default=None,
                        help='DB schema (do not include \'.\').')
    parser.add_argument('-v', '--verbose', action='store', type=int, default=0,
                        help='Verbosity (defualt:0; currently values up to 4)')
    parser.add_argument('--pizza-cutter-yaml', action='store', default=None,
                        help='Path + Base Filename with metadetect pizza-cutter YAML information.')
    parser.add_argument('--gaia-cat', action='store', default=None,
                        help='Path + Base Filename with GAIA source information (for pizza-cutter YAML).')
    parser.add_argument('--target_path', action='store', type=str, default=None,
                        help='Config file, when present is used to override/replace archive filepaths with relative filepath on target machine.')
    parser.add_argument('--me_proctag', action='store', type=str, default=None,
                        help='Multi-Epoch Processing Tag from which to draw MEDs inputs. Required for pizza cutter yaml generation.')
    parser.add_argument('--tilename', action='store', type=str, default=None,
                        help='Tilename (as an alternative to using -A to specify a COADD run, requires use of --me_proctag')
    parser.add_argument('--sel_band', action='store', type=str, default=None,
                        help='Only use sel_band on text list created')
    args = parser.parse_args()
    if args.verbose:
        print("Args: ", args)

    #
    #   Handle simple args (verbose, Schema, PFW_ATTEMPT_ID)
    #
    verbose = args.verbose

    if args.Schema is None:
        dbSchema = ""
    else:
        dbSchema = f"{args.Schema}."

    #
    #   Check whether a PFW_ATTEMPT_ID was provided (or if one needs to be determined from --tilename --me_proctag)
    #
    if (args.pfw_attempt_id is None):
        if (args.me_proctag is None)or(args.tilename is None):
            print("Must provide either a PFW_ATTEMPT_ID (-A) or PROCTAG and TILENAME (--me_proctag --tilename)")
            print("Aborting!")
            exit(1)

    ArchiveSite = args.archive
    MagBase = args.magbase

    #
    #   --pifftag is required if --usepiff is set
    #
    if args.usepiff:
        if args.pifftag is None:
            print("Aborting: when --usepiff is set --pifftag TAG is required.")
            exit(1)

    #
    #   Specify ZEROPOINT table for use
    #
    if args.zeropoint.upper() == "NONE":
        ZptInfo = None
        print(f" Proceeding with no ZEROPOINT table specified (mag_zero will be populated based on coadd_nwgint... or failing that will use fixed values of {MagBase:8.3f}")
    else:
        ZptInfo = {}
        if len(args.zeropoint.split('.')) > 1:
            ZptInfo['table'] = args.zeropoint
        else:
            ZptInfo['table'] = f'{dbSchema}{args.zeropoint}'
        print(f" Proceeding with constraints using {ZptInfo['table']:s} for ZEROPOINT constraints.")
        #
        #       Since a zeropoint table is being used... require that SOURCE and VERSION are present
        #
        if args.zsource is None or args.zversion is None:
            print(" As --zeropoint constraint is active:")
            if args.zsource is None:
                print("   --zsource {SOURCE} must be provided")
            if args.zversion is None:
                print("   --zversion {VERSION} must be provided")
            print(" Aborting!")
            exit(1)

    #
    #   Constraint on ZEROPOINT based on SOURCE
    #
    if args.zsource is not None:
        if ZptInfo is None:
            print(" No ZEROPOINT table specified. Constraint on {ZEROPOINT}.SOURCE ignored.")
        else:
            ZptInfo['source'] = args.zsource
            print(f"   Adding constraint on ZEROPOINT using SOURCE='{ZptInfo['source']:s}'.")
    else:
        if ZptInfo is not None:
            print("   Skipping constraint on ZEROPOINT using SOURCE")

    #
    #   Constraint on ZEROPOINT based on VERSION
    #
    if args.zversion is not None:
        if ZptInfo is None:
            print(" No ZEROPOINT table specified. Constraint on {ZEROPOINT}.VERSION ignored.")
        else:
            ZptInfo['version'] = args.zversion
            print(f"   Adding constraint on ZEROPOINT using VERSION='{ZptInfo['version']:s}'.")
    else:
        if ZptInfo is not None:
            print("   Skipping constraint on ZEROPOINT using VERSION")

    #
    #   Constraint on ZEROPOINT based on FLAGS
    #
    if args.zflag is not None:
        if ZptInfo is None:
            print(" No ZEROPOINT table specified. Constraint on {ZEROPOINT}.FLAG ignored.")
        else:
            ZptInfo['flag'] = args.zflag
            print(f"   Adding constraint on ZEROPOINT using FLAG<{ZptInfo['flag']:s}.")
    else:
        if ZptInfo is not None:
            print("   Skipping constraint on ZEROPOINT using FLAG")

    #
    #   Secondary ZEROPOINT capablity/constraint
    #
    if args.zpt2 is None:
        ZptSecondary = None
        print(" No secondary ZPT query requested.")
    else:
        ZptSecondary = {}
        if len(args.zpt2.split('.')) > 1:
            ZptSecondary['table'] = args.zpt2
        else:
            ZptSecondary['table'] = f'{dbSchema}{args.zpt2}'
        print(f" Proceeding with constraints for secondary  using {ZptSecondary['table']:s} for ZEROPOINT constraints.")
        #
        #       Since a zeropoint table is being used... require that SOURCE and VERSION are present
        #
        if args.z2source is None or args.z2version is None:
            print(" As --zpt2 constraint is active:")
            if args.z2source is None:
                print("   --z2source {SOURCE} must be provided")
            if args.z2version is None:
                print("   --z2version {VERSION} must be provided")
            print(" Aborting!")
            exit(1)
        #
        #       Constraint on secondary ZPT based on SOURCE
        #
        if args.z2source is not None:
            ZptSecondary['source'] = args.z2source
            print(f"   Adding constraint on Secondary ZPT using SOURCE='{ZptSecondary['source']:s}'.")
        #
        #       Constraint on secondary ZPT based on VERSION
        #
        if args.z2version is not None:
            ZptSecondary['version'] = args.z2version
            print(f"   Adding constraint on Secondary ZPT using VERSION='{ZptSecondary['version']:s}'.")
        #
        #       Constraint on secondary ZPT based on FLAGS
        #
        if args.z2flag is not None:
            ZptSecondary['flag'] = args.z2flag
            print(f"   Adding constraint on Secondary ZPT using FLAG<{ZptSecondary['flag']:s}.")

    #   Finished rationalizing input
    ########################################################
    #
    #   Setup a DB connection
    #
    try:
        desdmfile = os.environ["des_services"]
    except KeyError:
        desdmfile = None
    dbh = despydb.desdbi.DesDbi(desdmfile, args.section, retry=True)
    #    cur = dbh.cursor()

    if (args.pfw_attempt_id is None):
        IntID = mq.query_attempt_from_tag_tile(args.me_proctag,args.tilename,dbh,dbSchema,verbose)
        if (IntID is None):
            print("Failed to obtain a PFW_ATTEMPT_ID so will not be able to identify a run to base inputs on")
            print("Aborting")
            exit(1)
        PFWattemptID=str(IntID)
    else:
        PFWattemptID = args.pfw_attempt_id

    t0 = time.time()
    bands = args.bandlist.split(",")
    ImgDict, HeadDict = mq.query_imgs_from_attempt(PFWattemptID, bands, dbh, dbSchema, verbose)
    print(f"    Execution Time: {time.time() - t0:.2f}")
    print("    Img Dict size: ", len(ImgDict))
    print("    Head Dict size: ", len(HeadDict))

    #
    #   Now a bunch of rigamarole to get zeropoints
    #
    NeedZPT = False
    for Img in ImgDict:
        if 'mag_zero' not in ImgDict[Img]:
            NeedZPT = True
        else:
            if ImgDict[Img]['mag_zero'] is None:
                NeedZPT = True

    if not NeedZPT:
        print("All images already have zeropoints (inherited from a previous run/step).  Skipping further ZPT queries")
    else:
        if ZptInfo is not None:
            ImgDict = cq.query_zeropoint(ImgDict, ZptInfo, ZptSecondary, dbh, dbSchema, verbose)
            print("ZeroPoint query run ")
            print(f"    Execution Time: {time.time() - t0:.2f}")
            print("    Img Dict size: ", len(ImgDict))
        else:
        #
        #           Fallback assign value of MagBase for zeropoints.
        #
            for Img in ImgDict:
                if 'mag_zero' not in ImgDict[Img]:
                    ImgDict[Img]['mag_zero'] = MagBase
                else:
                    if ImgDict[Img]['mag_zero'] is None:
                        ImgDict[Img]['mag_zero'] = MagBase

    #
    #   Optional ability to obtain background and segmap images.
    #
    if args.bkgimg:
        BkgDict = cq.query_bkg_img(ImgDict, ArchiveSite, dbh, dbSchema, verbose)
        print(" Bkg image query run")
        print(f"    Execution Time: {time.time() - t0:.2f}")
        print("    Bkg Dict size: ", len(BkgDict))

    if args.segmap:
        SegDict = cq.query_segmap(ImgDict, ArchiveSite, dbh, dbSchema, verbose)
        print(" Segmentation Map query run")
        print("    Execution Time: {:.2f}".format(time.time() - t0))
        print("    Seg Dict size: ", len(SegDict))

    if args.psfmodel:
        if args.usepiff:
            PsfDict = cq.query_PIFFmodel(ImgDict, ArchiveSite, dbh, dbSchema, args.pifftag, verbose=verbose)
        else:
            PsfDict = cq.query_psfmodel(ImgDict, ArchiveSite, dbh, dbSchema, verbose=verbose)
        print(" PSF Model query run")
        print("    Execution Time: {:.2f}".format(time.time() - t0))
        print("    PSF Dict size: ", len(PsfDict))

    #
    #   Close DB connection?
    #
    #    dbh.close()
    #
    #   If a high level of verbosity is present print the query results.
    #
    if verbose > 2:
        print("Query results for COADD (SWarp) inputs, prior to mixing among catalogs")
        for Img in ImgDict:
            print(f" {ImgDict[Img]['expnum']:8d} {ImgDict[Img]['ccdnum']:2d} {ImgDict[Img]['band']:5s} {ImgDict[Img]['fluxscale']:6.3f} {ImgDict[Img]['filename']:s}")

    #
    #   Convert the ImgDict to an LLD (list of list of dictionaries)
    #   While doing the assembly get a count of number of Imgs per band
    #
    OutDict = {}
    for Img in ImgDict:
        wrec = True
        if Img not in HeadDict:
            wrec = False
        if args.segmap:
            if Img not in SegDict:
                wrec = False
        if args.bkgimg:
            if Img not in BkgDict:
                wrec = False
        if args.psfmodel:
            if Img not in PsfDict:
                wrec = False
        if wrec:
            OutDict[Img] = {}
            OutDict[Img]['red'] = ImgDict[Img]
            OutDict[Img]['head'] = HeadDict[Img]
            if args.segmap:
                OutDict[Img]['seg'] = SegDict[Img]
            if args.bkgimg:
                OutDict[Img]['bkg'] = BkgDict[Img]
            if args.psfmodel:
                OutDict[Img]['psf'] = PsfDict[Img]

    filetypes = ['red', 'head']
    mdatatypes = {'red': ['filename', 'compression', 'expnum', 'ccdnum', 'band', 'mag_zero'],
                  'head': ['filename', 'compression', 'expnum', 'ccdnum', 'band']}
    if args.segmap:
        filetypes.append('seg')
        mdatatypes['seg'] = ['filename', 'compression', 'expnum', 'ccdnum', 'band']
    if args.bkgimg:
        filetypes.append('bkg')
        mdatatypes['bkg'] = ['filename', 'compression', 'expnum', 'ccdnum', 'band']
    if args.psfmodel:
        filetypes.append('psf')
        mdatatypes['psf'] = ['filename', 'compression', 'expnum', 'ccdnum', 'band']

    Img_LLD = cq.ImgDict_to_LLD(OutDict, filetypes, mdatatypes, verbose)

    #
    #   If a high level of verbosity is present print the results.
    #
    if verbose > 3:
        print("Query results for COADD (SWarp) inputs (LLD format).")
        for Img in Img_LLD:
            print(Img)
    #
    #   Here a function call is needed to take the Img_LLD and write results to the output file.
    #
    Img_lines = queryutils.convert_multiple_files_to_lines(Img_LLD, filetypes)
    queryutils.output_lines(args.outfile, Img_lines)

    #
    #   Secondary (optional) output of a list of images found by the query.
    #
    if args.imglist is not None:
        imgfile = open(args.imglist, 'w')
        for Img in ImgDict:
            wrec = True
            if Img not in HeadDict:
                wrec = False
            if args.segmap:
                if Img not in SegDict:
                    wrec = False
            if args.bkgimg:
                if Img not in BkgDict:
                    wrec = False
            if args.psfmodel:
                if Img not in PsfDict:
                    wrec = False
            if wrec:
                imgfile.write(f" {ImgDict[Img]['expnum']:8d} {ImgDict[Img]['ccdnum']:2d} {ImgDict[Img]['band']:5s} {ImgDict[Img]['mag_zero']:8.5f}\n")
        imgfile.close()

    #   Close up shop.

    # Optional print a list of the location of the inputs
    if args.ima_list:
        mepochmisc.write_textlist(dbh, ImgDict, args.ima_list, sel_band=args.sel_band, fields=['fullname', 'mag_zero'], verb=args.verbose)
    if args.head_list:
        mepochmisc.write_textlist(dbh, HeadDict, args.head_list, sel_band=args.sel_band, fields=['fullname'], verb=args.verbose)
    if args.bkg_list:
        if not args.bkgimg:
            print(f"Warning: No --bkgimg search requested.  Skipping write for --bkg_list {args.bkg_list:s}")
        else:
            mepochmisc.write_textlist(dbh, BkgDict, args.bkg_list, sel_band=args.sel_band, fields=['fullname'], verb=args.verbose)
    if args.seg_list:
        if not args.segmap:
            print(f"Warning: No --segmap search requested.  Skipping write for --seg_list {args.seg_list:s}")
        else:
            mepochmisc.write_textlist(dbh, SegDict, args.seg_list, sel_band=args.sel_band, fields=['fullname'], verb=args.verbose)
    if args.psf_list:
        if not args.psfmodel:
            print(f"Warning: No --psfmodel search requested.  Skipping write for --psf_list {args.psf_list:s}")
        else:
            mepochmisc.write_textlist(dbh, PsfDict, args.psf_list, sel_band=args.sel_band, fields=['fullname'], verb=args.verbose)

    if args.pizza_cutter_yaml:
        bands = args.bandlist.split(",")
        tilename = mdetpizza.get_tilename_from_attempt(
            PFWattemptID,
            args.me_proctag,
            dbh,
            dbSchema,
            Timing=True,
            verbose=verbose,
        )
        coadd_data = {}
        for band in bands:
            coadd_data[band] = mdetpizza.get_coadd_info_from_attempt(
                tilename, band, PFWattemptID, args.me_proctag, dbh, dbSchema,
                Timing=True, verbose=verbose,
            )
#
#       For the case where pizza-cutter yaml is being generated for use on a target machine
#           use values in config file args.target_path to override/replace fullpaths from
#           archive with appropriate paths on the target machine
#
        if (args.target_path is None):
            if (verbose > 0):
                print("Using full archive paths in YAML generation")

            # MRB: used for local testing - comment out when not needed
            # ImgDict = mepochmisc.update_fullname(ImgDict, "JUNK")
            # HeadDict = mepochmisc.update_fullname(HeadDict, "JUNK")
            # BkgDict = mepochmisc.update_fullname(BkgDict, "JUNK")
            # SegDict = mepochmisc.update_fullname(SegDict, "JUNK")
            # if args.usepiff:
            #     PsfDict = mepochmisc.update_fullname(PsfDict, "JUNK")
            # else:
            #     PsfDict = mepochmisc.update_fullname(PsfDict, "JUNK")
        else:
            if (os.path.isfile(args.target_path)):
                tpath_Dict = mepochmisc.read_target_path(args.target_path,verbose=verbose)
                if (verbose > 0):
                    print("Adjusting filename paths to conform to target machine in YAML generation")
                for band in bands:
                    for ftype in coadd_data[band]:
                        if (ftype not in tpath_Dict):
                            print("No target side path available for filetype={:s}".format(ftype))
                            print(ftype,coadd_data[band][ftype]['fullname'])
                        else:
                            coadd_data[band][ftype]['fullname']=tpath_Dict[ftype]+'/'+coadd_data[band][ftype]['filename']+coadd_data[band][ftype]['compression']
                for ftype in ['red_immask','red_segmap','coadd_head_scamp','red_bkg','piff_model','psfex_model']:
                    miss_ftype=False
                    if (ftype not in tpath_Dict):
                        print("Target path specification for filetype: {:s} missing! Aborting!".format(ftype))
                        miss_ftype=True
                    if (miss_ftype):
                        exit(1)

                ImgDict  = mepochmisc.update_fullname(ImgDict,tpath_Dict['red_immask'])
                HeadDict = mepochmisc.update_fullname(HeadDict,tpath_Dict['coadd_head_scamp'])
                BkgDict  = mepochmisc.update_fullname(BkgDict,tpath_Dict['red_bkg'])
                SegDict  = mepochmisc.update_fullname(SegDict,tpath_Dict['red_segmap'])
                if args.usepiff:
                    PsfDict = mepochmisc.update_fullname(PsfDict,tpath_Dict['piff_model'])
                else:
                    PsfDict = mepochmisc.update_fullname(PsfDict,tpath_Dict['psfex_model'])

#
#       Go on and form pizza-cutter YAML
#
        if (verbose > 0):
            print("Forming pizza-cutter YAML files")

        yaml_data = mdetpizza.make_pizza_cutter_yaml(
            PFWattemptID, tilename, args.gaia_cat,
            ImgDict, HeadDict, BkgDict, SegDict, PsfDict,
            bands, coadd_data,
        )
        mdetpizza.add_coaddtile_geom(
            yaml_data, tilename, dbh, dbSchema, Timing=True, verbose=verbose
        )
        if args.usepiff and args.pifftag:
            mdetpizza.add_piff_info_to_yaml(
                    yaml_data, args.pifftag, dbh, dbSchema, Timing=True, verbose=verbose
                )

        for band in bands:
            with open(args.pizza_cutter_yaml + f"_{band}.yaml", "w") as fp:
                fp.write(yaml.dump(yaml_data[band], default_flow_style=False))

    exit()
